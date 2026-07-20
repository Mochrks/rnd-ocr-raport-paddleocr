"""
app/api/v1/endpoints/ocr.py
============================
HTTP handlers untuk OCR report card.

Endpoints:
  POST /api/v1/ocr/paddle                      — Upload + proses OCR, langsung return hasil
  GET  /api/v1/ocr/paddle/debug/{documentId}   — Raw OCR output untuk diagnosa

Rules:
- No business logic.
- No OCR processing.
- No data transformation beyond Pydantic serialization.
- Only: receive HTTP request → validate → call use case → return response.
"""

from __future__ import annotations

import logging
import os
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.api.deps import get_document_store
from app.application.ocr_use_case import run_ocr_pipeline
from app.core.config import settings
from app.infrastructure.storage.base import BaseDocumentStore
from app.schemas.ocr_schemas import OCRResultResponse
from app.services.ocr_orchestrator import debug_ocr_raw_text
from app.services.response_builder import (
    build_attendance_response,
    build_personality_response,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# Pastikan upload directory ada
os.makedirs(settings.upload_dir, exist_ok=True)


# ── POST /paddle ───────────────────────────────────────────────────────────

@router.post(
    "/paddle",
    response_model=OCRResultResponse,
    status_code=200,
    summary="OCR via PaddleOCR",
    description=(
        "Upload gambar atau PDF raport sekolah Indonesia. "
        "Diproses menggunakan PaddleOCR dan langsung mengembalikan hasil ekstraksi."
    ),
    tags=["OCR"],
)
async def paddle_ocr(
    file: UploadFile = File(
        ...,
        description="File raport: PDF, PNG, JPG, atau JPEG.",
    ),
    document_store: BaseDocumentStore = Depends(get_document_store),
) -> OCRResultResponse:
    """
    Upload raport dan ekstrak data menggunakan PaddleOCR secara sinkronus.

    Supported formats: PNG, JPG, JPEG, PDF.
    Returns: OCRResultResponse dengan subjects, personality, attendance.
    """
    filename = file.filename or "upload.png"
    ext = os.path.splitext(filename.lower())[1]

    # Validasi tipe file
    if ext not in settings.allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Tipe file tidak didukung: '{filename}'. "
                f"Format yang diizinkan: {', '.join(settings.allowed_extensions)}"
            ),
        )

    # Baca dan validasi ukuran file
    content = await file.read()
    size_mb = len(content) / (1024 * 1024)
    if size_mb > settings.max_upload_size_mb:
        raise HTTPException(
            status_code=413,
            detail=(
                f"Ukuran file {size_mb:.1f} MB melebihi batas maksimum "
                f"{settings.max_upload_size_mb} MB."
            ),
        )

    # Generate doc ID dan simpan ke disk
    doc_id = f"PDL{uuid.uuid4().hex[:8].upper()}"
    file_path = os.path.join(settings.upload_dir, f"{doc_id}_{filename}")

    with open(file_path, "wb") as fp:
        fp.write(content)

    logger.info(
        f"[PADDLE] Upload received | "
        f"doc_id={doc_id} | file={filename} | size={size_mb:.2f}MB"
    )

    # Daftarkan dokumen ke store
    document_store.create(doc_id, file_path)

    # Jalankan OCR pipeline secara sinkronus
    try:
        run_ocr_pipeline(doc_id, file_path)
    except Exception as exc:
        logger.error(f"[PADDLE] Pipeline error: {exc}", exc_info=True)

    # Ambil hasil
    record = document_store.get(doc_id)
    if not record:
        raise HTTPException(status_code=500, detail="Document record hilang setelah diproses.")

    if record.status == "FAILED":
        raise HTTPException(
            status_code=500,
            detail=f"OCR gagal: {record.error or 'Unknown error'}",
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


# ── GET /paddle/debug/{documentId} ────────────────────────────────────────

@router.get(
    "/paddle/debug/{documentId}",
    summary="Debug raw OCR output",
    description=(
        "Mengembalikan raw output PaddleOCR untuk dokumen yang sudah diproses. "
        "Berguna untuk diagnosa hasil ekstraksi."
    ),
    tags=["OCR"],
    include_in_schema=True,
)
async def debug_paddle_ocr(
    documentId: str,
    document_store: BaseDocumentStore = Depends(get_document_store),
):
    """
    Debug endpoint — raw OCR text, bounding boxes, detected rows, dan column layout
    untuk dokumen yang sudah diupload sebelumnya.

    Args:
        documentId: Document ID yang dikembalikan oleh POST /paddle.
    """
    record = document_store.get(documentId)
    if record is None:
        raise HTTPException(
            status_code=404,
            detail=f"Document tidak ditemukan: '{documentId}'",
        )

    image_path = record.image_path
    if not image_path or not os.path.exists(image_path):
        raise HTTPException(
            status_code=404,
            detail="File gambar tidak ditemukan di disk.",
        )

    return debug_ocr_raw_text(image_path)
