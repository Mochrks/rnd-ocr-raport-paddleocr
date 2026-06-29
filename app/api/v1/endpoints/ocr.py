"""
app/api/v1/endpoints/ocr.py
============================
HTTP handlers for the OCR report card endpoints.

Rules for this file:
- No business logic.
- No OCR processing.
- No data transformation beyond serializing Pydantic models.
- Only: receive HTTP request → call use case → return response.

Endpoints (unchanged from original):
  POST /api/v1/academic/report/upload
  GET  /api/v1/academic/report/{documentId}/debug
"""

from __future__ import annotations

import logging
import os
import uuid

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.application.ocr_use_case import run_ocr_pipeline
from app.core.config import settings
from app.core.exceptions import DocumentNotFoundError, UnsupportedFileTypeError
from app.infrastructure.storage.document_store import document_store
from app.schemas.ocr_schemas import OCRResultResponse
from app.services.ocr_orchestrator import debug_ocr_raw_text
from app.services.response_builder import (
    build_attendance_response,
    build_personality_response,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# Ensure upload directory exists
os.makedirs(settings.upload_dir, exist_ok=True)


@router.post("/report/upload", response_model=OCRResultResponse)
async def upload_report(file: UploadFile = File(...)):
    """
    Upload a report card image or PDF and extract academic data via OCR.

    Supported formats: PNG, JPG, JPEG, PDF.

    Returns:
        OCRResultResponse with subjects, personality, attendance, accuracy,
        processing time, and document ID.
    """
    filename = file.filename or "unknown.png"
    ext = os.path.splitext(filename.lower())[1]

    if ext not in settings.allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: '{filename}'. "
                   f"Allowed: {', '.join(settings.allowed_extensions)}",
        )

    doc_id = f"DOC{uuid.uuid4().hex[:8].upper()}"
    file_path = os.path.join(settings.upload_dir, f"{doc_id}_{filename}")

    # Save file to disk
    content = await file.read()
    with open(file_path, "wb") as fp:
        fp.write(content)

    # Register the document before processing
    document_store.create(doc_id, file_path)

    # Run the OCR pipeline (synchronous for now)
    run_ocr_pipeline(doc_id, file_path)

    # Read back the result
    record = document_store.get(doc_id)
    if record is None:
        raise HTTPException(status_code=500, detail="Document record lost after processing.")

    personality_resp = build_personality_response(record.personality)
    attendance_resp = build_attendance_response(record.attendance)

    return OCRResultResponse(
        documentId=record.id,
        status=record.status,
        accuracy=record.accuracy,
        processingTime=record.processing_time,
        subjects=record.extracted_data,
        personality=personality_resp,
        attendance=attendance_resp,
    )


@router.get("/report/{documentId}/debug")
async def debug_ocr(documentId: str):
    """
    Debug endpoint — return raw PaddleOCR text, bounding boxes, detected rows,
    and column layout for a previously uploaded document.

    Args:
        documentId: The document ID returned by POST /report/upload.
    """
    record = document_store.get(documentId)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Document not found: '{documentId}'")

    image_path = record.image_path
    if not image_path or not os.path.exists(image_path):
        raise HTTPException(status_code=404, detail="Image file not found on disk.")

    return debug_ocr_raw_text(image_path)
