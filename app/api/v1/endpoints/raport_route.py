"""
app/api/v1/endpoints/ocr.py
============================
HTTP handlers untuk OCR report card.

Endpoints:
  POST /api/v1/ocr/raport                      — Upload + proses OCR, langsung return hasil

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
from app.services.response_builder import (
    build_attendance_response,
    build_personality_response,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# Pastikan upload directory ada
os.makedirs(settings.upload_dir, exist_ok=True)


# ── POST /raport ───────────────────────────────────────────────────────────

@router.post(
    "/raport",
    response_model=OCRResultResponse,
    status_code=200,
    summary="OCR Engine Paddle",
    description=(
        "Upload gambar atau PDF raport sekolah Indonesia. "
        "Diproses menggunakan PaddleOCR dan langsung mengembalikan hasil ekstraksi."
    ),
    tags=["OCR Paddle"],
)
async def raport_ocr(
    file: UploadFile = File(
        ...,
        description="File raport: PDF, PNG, JPG, atau JPEG.",
    ),
    document_store: BaseDocumentStore = Depends(get_document_store),
) -> OCRResultResponse:
    from app.infrastructure.data.db_client import get_use_ai_ocr_flag
    from app.api.v1.endpoints.ai_route import _handle_ai_raport_upload
    
    use_ai = await get_use_ai_ocr_flag()
    if use_ai:
        return await _handle_ai_raport_upload(file, "qwen", document_store)
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
