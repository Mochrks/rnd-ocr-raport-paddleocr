"""
app/application/ocr_use_case.py
================================
Application-layer use case: process an uploaded report card image end-to-end.

This is the single entry point called by the API endpoint. It:
1. Creates a document record in the store
2. Runs the OCR pipeline with timing
3. Persists results back to the store
4. Returns the populated record

The API layer (ocr.py) should call run_ocr_pipeline() and then read back
the record — it has no knowledge of the OCR pipeline internals.
"""

from __future__ import annotations

import logging
import time
from typing import Dict, List

from app.core.logging import PhaseLogger
from app.domain.constants import MASTER_SUBJECTS
from app.infrastructure.storage.document_store import DocumentStore, document_store
from app.services.ocr_orchestrator import perform_ocr_and_extract_full

logger = logging.getLogger(__name__)


def run_ocr_pipeline(document_id: str, image_path: str) -> None:
    """
    Execute the full OCR pipeline for an uploaded document.

    Reads the image, runs OCR extraction, computes timing, and updates
    the document record in the store with the result (SUCCESS or FAILED).

    This function is synchronous and runs in the FastAPI request handler.
    For async/background processing, wrap it in asyncio.run_in_executor().

    Args:
        document_id: The document ID created before upload (e.g. "DOC1A2B3C4").
        image_path:  Path to the uploaded file on disk.
    """
    phase = PhaseLogger(logger, doc_id=document_id)
    start_time = time.perf_counter()

    try:
        with phase.time("OCR pipeline"):
            full_result = perform_ocr_and_extract_full(image_path, MASTER_SUBJECTS)

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
            f"[{document_id}] Pipeline complete | "
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
            f"[{document_id}] Pipeline FAILED | elapsed={processing_time}s | error={exc}",
            exc_info=True,
        )
