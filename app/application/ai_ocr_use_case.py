"""
app/application/ai_ocr_use_case.py
=====================================
Application-layer use case: process an uploaded report card image using
an AI Vision model (DeepSeek or Qwen) as the OCR engine.

Flow:
  1. Create document record in the store
  2. If PDF → convert to images (reuse existing pdf_converter)
  3. For each image → call AI client → parse JSON → map to pipeline dict
  4. Merge multi-page results
  5. Persist result and return

This use case is intentionally parallel in structure to the PaddleOCR
use case (`ocr_use_case.py`) so both share the same caller interface:
  `run_ai_ocr_pipeline(document_id, image_path, engine)`

The engine parameter determines which AI client to use, keeping this
use case DRY and extensible.
"""

from __future__ import annotations

import json
import logging
import os
import re
import tempfile
import time
from typing import Any, Dict, List, Optional

from app.api.deps import get_document_store
from app.core.exceptions import AIInvalidResponseError
from app.core.logging import PhaseLogger
from app.domain.ai_vision_dto import AIVisionRawResponse
from app.infrastructure.ai.base_client import BaseAIClient
from app.infrastructure.ai.qwen_client import QwenClient
from app.infrastructure.ocr.pdf_converter import convert_pdf_to_images
from app.services.ai_response_mapper import map_ai_response_to_pipeline_dict

logger = logging.getLogger(__name__)


# ── Engine registry ───────────────────────────────────────────────────────

def get_ai_client(engine: str) -> BaseAIClient:
    """
    Factory: return the appropriate AI client for the given engine name.

    Args:
        engine: One of "deepseek", "qwen", "gemini", "groq" (case-insensitive).

    Returns:
        Instantiated AI client.

    Raises:
        ValueError: If the engine name is not recognized.
    """
    engine_lower = engine.lower()
    if engine_lower == "qwen":
        from app.infrastructure.ai.qwen_client import QwenClient
        return QwenClient()
    raise ValueError(f"Unknown AI engine: '{engine}'. Valid: qwen")


# ── Public API ─────────────────────────────────────────────────────────────

async def run_ai_ocr_pipeline(
    document_id: str,
    image_path: str,
    engine: str,
) -> None:
    """
    Execute the full AI Vision OCR pipeline for an uploaded document.

    This is the async entry point called by the FastAPI endpoint.
    Uses an AI Vision model (DeepSeek or Qwen) instead of PaddleOCR.

    Args:
        document_id: Document ID created before upload.
        image_path:  Path to the uploaded file on disk.
        engine:      AI engine name: "deepseek" or "qwen".
    """
    phase = PhaseLogger(logger, doc_id=document_id)
    start_time = time.perf_counter()
    document_store = get_document_store()

    try:
        client = get_ai_client(engine)

        with phase.time(f"AI OCR pipeline [{client.engine_name}]"):
            full_result = await _process_file(image_path, client)

        subjects = full_result.get("subjects", [])
        personality = full_result.get("personality")
        attendance = full_result.get("attendance")
        processing_time = round(time.perf_counter() - start_time, 2)

        document_store.mark_success(
            document_id=document_id,
            extracted_data=subjects,
            personality=personality,
            attendance=attendance,
            processing_time=processing_time,
        )

        logger.info(
            f"[{document_id}] ✅ AI Pipeline [{client.engine_name}] complete | "
            f"subjects={len(subjects)} | "
            f"personality={'yes' if personality else 'no'} | "
            f"attendance={'yes' if attendance else 'no'} | "
            f"elapsed={processing_time}s"
        )

    except Exception as exc:
        processing_time = round(time.perf_counter() - start_time, 2)
        document_store.mark_failed(
            document_id=document_id,
            error=str(exc),
            processing_time=processing_time,
        )
        logger.error(
            f"[{document_id}] ❌ AI Pipeline [{engine}] FAILED | "
            f"elapsed={processing_time}s | error={exc}",
            exc_info=True,
        )
        raise


async def run_generic_ai_ocr(
    file_path: str,
    engine: str,
    doc_type: str,
) -> Dict[str, Any]:
    """
    Execute a generic AI OCR extraction for KTP, KK, Akta, or KP.
    Returns the parsed dictionary directly.
    """
    start_time = time.perf_counter()
    client = get_ai_client(engine)

    try:
        raw_text = await client.run_ocr(file_path, doc_type=doc_type)

        # Basic JSON parsing
        import re
        cleaned = re.sub(r"```(?:json)?\s*", "", raw_text, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r"```\s*$", "", cleaned).strip()

        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise AIInvalidResponseError(
                client.engine_name,
                f"No valid JSON object found in response. "
                f"First 200 chars: {cleaned[:200]!r}",
            )

        json_str = cleaned[start : end + 1]
        
        import json
        parsed_dict = json.loads(json_str)

        elapsed = round(time.perf_counter() - start_time, 2)
        logger.info(
            f"[{client.engine_name}] Generic AI OCR ({doc_type}) complete | "
            f"elapsed={elapsed}s"
        )
        return parsed_dict

    except Exception as exc:
        logger.error(
            f"[{client.engine_name}] Generic AI OCR ({doc_type}) FAILED | error={exc}",
            exc_info=True,
        )
        raise


# ── File Processing ────────────────────────────────────────────────────────

async def _process_file(
    file_path: str,
    client: BaseAIClient,
) -> Dict[str, Any]:
    """
    Process an uploaded file (PDF or image) using the AI client.

    For PDFs: converts to images, processes each page, merges results.
    For images: processes directly.

    Args:
        file_path: Path to the uploaded file.
        client:    Instantiated AI client.

    Returns:
        Unified pipeline dict: { subjects, personality, attendance }
    """
    if file_path.lower().endswith(".pdf"):
        return await _process_pdf(file_path, client)
    return await _process_single_image(file_path, client)


async def _process_pdf(
    pdf_path: str,
    client: BaseAIClient,
) -> Dict[str, Any]:
    """Convert PDF pages to images and process each page with the AI client."""
    all_subjects: List[Dict] = []
    personality: Optional[Dict] = None
    attendance: Optional[Dict] = None
    seen_ids: set = set()

    t0 = time.perf_counter()

    with tempfile.TemporaryDirectory() as tmp_dir:
        try:
            image_paths = convert_pdf_to_images(pdf_path, output_dir=tmp_dir)
        except Exception as exc:
            logger.error(f"[{client.engine_name}] PDF conversion failed: {exc}")
            return {"subjects": [], "personality": None, "attendance": None}

        if not image_paths:
            logger.error(f"[{client.engine_name}] No images extracted from PDF")
            return {"subjects": [], "personality": None, "attendance": None}

        logger.info(
            f"[{client.engine_name}] PDF → {len(image_paths)} pages "
            f"({time.perf_counter() - t0:.2f}s)"
        )

        for idx, img_path in enumerate(image_paths):
            try:
                result = await _process_single_image(img_path, client)
                for subj in result.get("subjects", []):
                    if subj["subjectId"] not in seen_ids:
                        seen_ids.add(subj["subjectId"])
                        all_subjects.append(subj)
                if personality is None and result.get("personality"):
                    personality = result["personality"]
                if attendance is None and result.get("attendance"):
                    attendance = result["attendance"]
            except Exception as exc:
                logger.warning(
                    f"[{client.engine_name}] Error processing PDF page {idx}: {exc}"
                )

    logger.info(
        f"[{client.engine_name}] PDF total: {time.perf_counter() - t0:.2f}s | "
        f"{len(image_paths)} pages | {len(all_subjects)} subjects"
    )

    return {
        "subjects": all_subjects,
        "personality": personality,
        "attendance": attendance,
    }


async def _process_single_image(
    image_path: str,
    client: BaseAIClient,
) -> Dict[str, Any]:
    """
    Send a single image to the AI client and map the response.

    Args:
        image_path: Path to the image file.
        client:     Instantiated AI client.

    Returns:
        Unified pipeline dict: { subjects, personality, attendance }
    """
    t0 = time.perf_counter()

    # Call AI service
    raw_text = await client.run_ocr(image_path)

    logger.info(
        f"[{client.engine_name}] Raw response received | "
        f"length={len(raw_text)} | "
        f"inference_time={time.perf_counter() - t0:.2f}s"
    )

    # Parse raw text as structured JSON
    ai_dto = _parse_ai_response(raw_text, client.engine_name)

    # Map to unified pipeline dict
    return map_ai_response_to_pipeline_dict(ai_dto, client.engine_name)


# ── JSON Parsing ───────────────────────────────────────────────────────────

def _parse_ai_response(
    raw_text: str,
    engine_name: str,
) -> AIVisionRawResponse:
    """
    Parse the AI model's raw text output into an AIVisionRawResponse DTO.

    Handles common model output issues:
    - Markdown code fences (```json ... ```)
    - Leading/trailing whitespace
    - Partial JSON (invalid) → raises AIInvalidResponseError

    Args:
        raw_text:    Raw text from the AI model.
        engine_name: Engine name for error messages.

    Returns:
        Validated AIVisionRawResponse.

    Raises:
        AIInvalidResponseError: If text cannot be parsed to valid JSON
                                or fails Pydantic validation.
    """
    # Strip markdown code fences
    cleaned = re.sub(r"```(?:json)?\s*", "", raw_text, flags=re.IGNORECASE).strip()
    # Remove any trailing ``` that remained
    cleaned = re.sub(r"```\s*$", "", cleaned).strip()

    if not cleaned:
        raise AIInvalidResponseError(engine_name, "Empty response after stripping markdown")

    # Find the outermost JSON object
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise AIInvalidResponseError(
            engine_name,
            f"No valid JSON object found in response. "
            f"First 200 chars: {cleaned[:200]!r}",
        )

    json_str = cleaned[start : end + 1]

    try:
        parsed_dict = json.loads(json_str)
    except json.JSONDecodeError as exc:
        raise AIInvalidResponseError(
            engine_name,
            f"JSON decode error: {exc}. "
            f"First 300 chars: {json_str[:300]!r}",
        ) from exc

    try:
        return AIVisionRawResponse.model_validate(parsed_dict)
    except Exception as exc:
        raise AIInvalidResponseError(
            engine_name,
            f"Pydantic validation failed: {exc}",
        ) from exc
