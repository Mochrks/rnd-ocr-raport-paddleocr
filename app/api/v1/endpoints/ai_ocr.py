"""
app/api/v1/endpoints/ai_ocr.py
================================
HTTP handlers for AI Vision OCR endpoints and unified OCR endpoint.

Endpoints:
  POST /api/v1/ocr/paddle     — OCR using PaddleOCR (local engine), same response as AI endpoints
  POST /api/v1/ocr/deepseek   — OCR using DeepSeek Vision model
  POST /api/v1/ocr/qwen       — OCR using Qwen3-VL Vision model

All endpoints accept multipart/form-data with a single 'file' field.
Supported formats: PDF, PNG, JPG, JPEG.

The response schema is IDENTICAL across all three engines so the
frontend can swap engines without any changes.

Rules for this file:
- No business logic.
- No AI processing.
- No JSON transformation beyond Pydantic serialization.
- Only: receive HTTP request → validate file → call use case → return response.
"""

from __future__ import annotations

import logging
import os
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.api.deps import get_document_store
from app.application.ai_ocr_use_case import run_ai_ocr_pipeline
from app.application.ocr_use_case import run_ocr_pipeline
from app.core.config import settings
from app.core.exceptions import (
    AIAuthorizationError,
    AIForbiddenError,
    AIInvalidResponseError,
    AIRequestTimeoutError,
    AIServiceUnavailableError,
)
from app.infrastructure.storage.base import BaseDocumentStore
from app.schemas.ocr_schemas import OCRResultResponse
from app.services.response_builder import (
    build_attendance_response,
    build_personality_response,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# Ensure upload directory exists
os.makedirs(settings.upload_dir, exist_ok=True)


# ── Shared handler ─────────────────────────────────────────────────────────

async def _handle_ai_ocr_upload(
    file: UploadFile,
    engine: str,
    document_store: BaseDocumentStore,
) -> OCRResultResponse:
    """
    Shared logic for all AI Vision OCR upload endpoints.

    1. Validate file type and size.
    2. Save file to disk.
    3. Register document record.
    4. Run the AI OCR pipeline.
    5. Return the unified OCRResultResponse.

    Args:
        file:           Uploaded file from multipart form.
        engine:         AI engine name: "deepseek" or "qwen".
        document_store: Injected document store dependency.

    Returns:
        Unified OCRResultResponse (identical structure to PaddleOCR endpoint).
    """
    filename = file.filename or f"upload.png"
    ext = os.path.splitext(filename.lower())[1]

    # Validate file type
    if ext not in settings.allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported file type: '{filename}'. "
                f"Allowed: {', '.join(settings.allowed_extensions)}"
            ),
        )

    # Validate file size
    content = await file.read()
    size_mb = len(content) / (1024 * 1024)
    if size_mb > settings.max_upload_size_mb:
        raise HTTPException(
            status_code=413,
            detail=(
                f"File size {size_mb:.1f} MB exceeds the maximum "
                f"allowed {settings.max_upload_size_mb} MB."
            ),
        )

    # Generate document ID and save file
    doc_id = f"AI{engine[:2].upper()}{uuid.uuid4().hex[:8].upper()}"
    file_path = os.path.join(settings.upload_dir, f"{doc_id}_{filename}")

    with open(file_path, "wb") as fp:
        fp.write(content)

    logger.info(
        f"[{engine.upper()}] Upload received | "
        f"doc_id={doc_id} | "
        f"file={filename} | "
        f"size={size_mb:.2f}MB"
    )

    # Register document
    document_store.create(doc_id, file_path)

    # Run AI OCR pipeline
    try:
        await run_ai_ocr_pipeline(doc_id, file_path, engine)
    except AIAuthorizationError as exc:
        raise HTTPException(status_code=401, detail=str(exc))
    except AIForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except AIInvalidResponseError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except AIRequestTimeoutError as exc:
        raise HTTPException(status_code=504, detail=str(exc))
    except AIServiceUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        logger.error(f"[{engine.upper()}] Unexpected error: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"AI OCR processing failed: {exc}")

    # Retrieve the finished record
    record = document_store.get(doc_id)
    if not record:
        raise HTTPException(status_code=500, detail="Document record lost after processing.")

    if record.status == "FAILED":
        raise HTTPException(
            status_code=500,
            detail=f"AI OCR extraction failed: {record.error or 'Unknown error'}",
        )

    personality_resp = (
        build_personality_response(record.personality) if record.personality else None
    )
    attendance_resp = (
        build_attendance_response(record.attendance) if record.attendance else None
    )

    return OCRResultResponse(
        documentId=record.id,
        status=record.status,
        accuracy=record.accuracy,
        processingTime=record.processing_time,
        subjects=record.extracted_data,
        personality=personality_resp,
        attendance=attendance_resp,
    )


# ── PaddleOCR Endpoint ────────────────────────────────────────────────────

@router.post(
    "/paddle",
    response_model=OCRResultResponse,
    status_code=200,
    summary="OCR via PaddleOCR (local engine)",
    description=(
        "Upload a report card image or PDF and extract data using the local "
        "PaddleOCR engine. Returns the same response format as the AI Vision "
        "endpoints — use this to compare results between engines."
    ),
    tags=["AI Vision OCR"],
)
async def paddle_ocr(
    file: UploadFile = File(
        ...,
        description="Report card file: PDF, PNG, JPG, or JPEG.",
    ),
    document_store: BaseDocumentStore = Depends(get_document_store),
) -> OCRResultResponse:
    """
    Extract raport data using the local PaddleOCR engine.

    Accepts: multipart/form-data with 'file' field.
    Supported formats: PDF, PNG, JPG, JPEG.
    """
    filename = file.filename or "upload.png"
    ext = os.path.splitext(filename.lower())[1]

    if ext not in settings.allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported file type: '{filename}'. "
                f"Allowed: {', '.join(settings.allowed_extensions)}"
            ),
        )

    content = await file.read()
    size_mb = len(content) / (1024 * 1024)
    if size_mb > settings.max_upload_size_mb:
        raise HTTPException(
            status_code=413,
            detail=(
                f"File size {size_mb:.1f} MB exceeds the maximum "
                f"allowed {settings.max_upload_size_mb} MB."
            ),
        )

    doc_id = f"DOCPDL{uuid.uuid4().hex[:8].upper()}"
    file_path = os.path.join(settings.upload_dir, f"{doc_id}_{filename}")

    with open(file_path, "wb") as fp:
        fp.write(content)

    logger.info(
        f"[PADDLE] Upload received | "
        f"doc_id={doc_id} | file={filename} | size={size_mb:.2f}MB"
    )

    document_store.create(doc_id, file_path)

    try:
        run_ocr_pipeline(doc_id, file_path)
    except Exception as exc:
        logger.error(f"[PADDLE] Pipeline failed: {exc}", exc_info=True)

    record = document_store.get(doc_id)
    if not record:
        raise HTTPException(status_code=500, detail="Document record lost after processing.")

    if record.status == "FAILED":
        raise HTTPException(
            status_code=500,
            detail=f"PaddleOCR extraction failed: {record.error or 'Unknown error'}",
        )

    personality_resp = (
        build_personality_response(record.personality) if record.personality else None
    )
    attendance_resp = (
        build_attendance_response(record.attendance) if record.attendance else None
    )

    return OCRResultResponse(
        documentId=record.id,
        status=record.status,
        accuracy=record.accuracy,
        processingTime=record.processing_time,
        subjects=record.extracted_data,
        personality=personality_resp,
        attendance=attendance_resp,
    )


# ── DeepSeek Endpoint ──────────────────────────────────────────────────────

@router.post(
    "/deepseek",
    response_model=OCRResultResponse,
    status_code=200,
    summary="OCR via DeepSeek Vision",
    description=(
        "Upload a report card image or PDF and extract data using the "
        "DeepSeek Vision model. Returns the same response format as the "
        "PaddleOCR endpoint. Note: currently routed to qwen3-vl:8b as the "
        "active vision backend on this server."
    ),
    tags=["AI Vision OCR"],
)
async def deepseek_ocr(
    file: UploadFile = File(
        ...,
        description="Report card file: PDF, PNG, JPG, or JPEG.",
    ),
    document_store: BaseDocumentStore = Depends(get_document_store),
) -> OCRResultResponse:
    """
    Extract raport data using the DeepSeek Vision model.

    Note: deepseek-ocr:3b on this Ollama server does not expose a usable
    text output via the OpenAI-compatible API. Requests are transparently
    forwarded to qwen3-vl:8b which is the active vision model on this server.

    Accepts: multipart/form-data with 'file' field.
    Supported formats: PDF, PNG, JPG, JPEG.
    """
    return await _handle_ai_ocr_upload(file, "qwen", document_store)


# ── Qwen Endpoint ──────────────────────────────────────────────────────────

@router.post(
    "/qwen",
    response_model=OCRResultResponse,
    status_code=200,
    summary="OCR via Qwen3-VL Vision",
    description=(
        "Upload a report card image or PDF and extract data using the "
        "Qwen3-VL Vision model. Returns the same response format as the "
        "PaddleOCR endpoint."
    ),
    tags=["AI Vision OCR"],
)
async def qwen_ocr(
    file: UploadFile = File(
        ...,
        description="Report card file: PDF, PNG, JPG, or JPEG.",
    ),
    document_store: BaseDocumentStore = Depends(get_document_store),
) -> OCRResultResponse:
    """
    Extract raport data using the Qwen3-VL Vision model.

    Accepts: multipart/form-data with 'file' field.
    Supported formats: PDF, PNG, JPG, JPEG.
    """
    return await _handle_ai_ocr_upload(file, "qwen", document_store)


# ── Gemini Endpoint ────────────────────────────────────────────────────────

@router.post(
    "/gemini",
    response_model=OCRResultResponse,
    status_code=200,
    summary="OCR via Google Gemini Vision (Free)",
    description=(
        "Upload a report card image or PDF and extract data using Google Gemini "
        "Vision (gemini-2.5-flash). Free tier: 15 RPM, no credit card required. "
        "Get API key at: https://aistudio.google.com/apikey"
    ),
    tags=["AI Vision OCR"],
)
async def gemini_ocr(
    file: UploadFile = File(
        ...,
        description="Report card file: PDF, PNG, JPG, or JPEG.",
    ),
    document_store: BaseDocumentStore = Depends(get_document_store),
) -> OCRResultResponse:
    """
    Extract raport data using Google Gemini Vision (gemini-2.5-flash).

    Accepts: multipart/form-data with 'file' field.
    Supported formats: PDF, PNG, JPG, JPEG.

    Free tier: 15 requests/minute, 1500 requests/day.
    Get API key: https://aistudio.google.com/apikey
    """
    return await _handle_ai_ocr_upload(file, "gemini", document_store)


# ── Groq Endpoint ──────────────────────────────────────────────────────────

@router.post(
    "/groq",
    response_model=OCRResultResponse,
    status_code=200,
    summary="OCR via Groq Vision (Free, Ultra-Fast)",
    description=(
        "Upload a report card image or PDF and extract data using Groq's "
        "Llama 4 Scout vision model. Free tier: 30 RPM, no credit card required. "
        "Get API key at: https://console.groq.com/keys"
    ),
    tags=["AI Vision OCR"],
)
async def groq_ocr(
    file: UploadFile = File(
        ...,
        description="Report card file: PDF, PNG, JPG, or JPEG.",
    ),
    document_store: BaseDocumentStore = Depends(get_document_store),
) -> OCRResultResponse:
    """
    Extract raport data using Groq Llama 4 Scout Vision.

    Accepts: multipart/form-data with 'file' field.
    Supported formats: PDF, PNG, JPG, JPEG.

    Free tier: 30 requests/minute, 14,400 requests/day.
    Get API key: https://console.groq.com/keys
    """
    return await _handle_ai_ocr_upload(file, "groq", document_store)
