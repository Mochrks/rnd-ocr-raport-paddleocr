"""
app/api/v1/endpoints/ai_route.py
================================
HTTP handlers for AI Vision OCR endpoints (Qwen only).

Endpoints:
  POST /api/v1/ocr/ai/raport
  POST /api/v1/ocr/ai/ktp
  POST /api/v1/ocr/ai/kk
  POST /api/v1/ocr/ai/akta
  POST /api/v1/ocr/ai/kp

All endpoints accept multipart/form-data with a single 'file' field.
Supported formats: PDF, PNG, JPG, JPEG.
"""

from __future__ import annotations

import logging
import os
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.api.deps import get_document_store
from app.application.ai_ocr_use_case import run_ai_ocr_pipeline, run_generic_ai_ocr
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
from app.schemas.generic_response import GenericResponse, ErrorDetail
from app.services.response_builder import (
    build_attendance_response,
    build_personality_response,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai")

# Ensure upload directory exists
os.makedirs(settings.upload_dir, exist_ok=True)


# ── Shared handler for Raport ──────────────────────────────────────────────

async def _handle_ai_raport_upload(
    file: UploadFile,
    engine: str,
    document_store: BaseDocumentStore,
) -> OCRResultResponse:
    filename = file.filename or "upload.png"
    ext = os.path.splitext(filename.lower())[1]

    if ext not in settings.allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: '{filename}'. Allowed: {', '.join(settings.allowed_extensions)}",
        )

    content = await file.read()
    size_mb = len(content) / (1024 * 1024)
    if size_mb > settings.max_upload_size_mb:
        raise HTTPException(
            status_code=413,
            detail=f"File size {size_mb:.1f} MB exceeds max {settings.max_upload_size_mb} MB.",
        )

    doc_id = f"AI{engine[:2].upper()}{uuid.uuid4().hex[:8].upper()}"
    file_path = os.path.join(settings.upload_dir, f"{doc_id}_{filename}")

    with open(file_path, "wb") as fp:
        fp.write(content)

    logger.info(f"[{engine.upper()}] Upload received | doc_id={doc_id} | file={filename} | size={size_mb:.2f}MB")

    document_store.create(doc_id, file_path)

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

    record = document_store.get(doc_id)
    if not record:
        raise HTTPException(status_code=500, detail="Document record lost after processing.")

    if record.status == "FAILED":
        raise HTTPException(
            status_code=500,
            detail=f"AI OCR extraction failed: {record.error or 'Unknown error'}",
        )

    personality_resp = build_personality_response(record.personality) if record.personality else None
    attendance_resp = build_attendance_response(record.attendance) if record.attendance else None

    return OCRResultResponse(
        documentId=record.id,
        status=record.status,
        accuracy=record.accuracy,
        processingTime=record.processing_time,
        subjects=record.extracted_data,
        personality=personality_resp,
        attendance=attendance_resp,
    )


# ── Shared handler for KTP/KK/Akta/KP ──────────────────────────────────────

async def _handle_ai_generic_upload(
    file: UploadFile,
    engine: str,
    doc_type: str,
) -> GenericResponse:
    """
    Shared handler for generic documents (KTP, KK, Akta, KP) using AI Vision.
    Supports multiple engines: Qwen, DeepSeek/MiniCPM, etc.
    """
    filename = file.filename or "upload.png"
    ext = os.path.splitext(filename.lower())[1]

    if ext not in settings.allowed_extensions:
        return GenericResponse(
            status="error",
            code=400,
            message=f"Unsupported file type: '{filename}'. Allowed: {', '.join(settings.allowed_extensions)}",
            error=ErrorDetail(code="BAD_REQUEST", message="Unsupported file type")
        )

    content = await file.read()
    size_mb = len(content) / (1024 * 1024)
    if size_mb > settings.max_upload_size_mb:
        return GenericResponse(
            status="error",
            code=413,
            message=f"File size {size_mb:.1f} MB exceeds max {settings.max_upload_size_mb} MB.",
            error=ErrorDetail(code="PAYLOAD_TOO_LARGE", message="File too large")
        )

    doc_id = f"AI{engine[:2].upper()}{uuid.uuid4().hex[:8].upper()}"
    file_path = os.path.join(settings.upload_dir, f"{doc_id}_{filename}")

    with open(file_path, "wb") as fp:
        fp.write(content)

    logger.info(f"[{engine.upper()}] Upload received for {doc_type} | file={filename} | size={size_mb:.2f}MB")

    import time
    start_time = time.perf_counter()

    try:
        parsed_data = await run_generic_ai_ocr(file_path, engine, doc_type)
        elapsed = round(time.perf_counter() - start_time, 2)
        
        # Clean up temp file
        if os.path.exists(file_path):
            os.remove(file_path)

        return GenericResponse(
            status="success",
            code=200,
            message=f"{doc_type.upper()} data extracted successfully using AI ({engine})",
            data=parsed_data,
            raw_text=[],
            accuracy_percentage=100.0,
            elapsed_time=elapsed,
        )

    except AIAuthorizationError as exc:
        return GenericResponse(status="error", code=401, message=str(exc), error=ErrorDetail(code="UNAUTHORIZED", message=str(exc)))
    except AIForbiddenError as exc:
        return GenericResponse(status="error", code=403, message=str(exc), error=ErrorDetail(code="FORBIDDEN", message=str(exc)))
    except AIInvalidResponseError as exc:
        return GenericResponse(status="error", code=422, message=str(exc), error=ErrorDetail(code="UNPROCESSABLE_ENTITY", message=str(exc)))
    except AIRequestTimeoutError as exc:
        return GenericResponse(status="error", code=504, message=str(exc), error=ErrorDetail(code="GATEWAY_TIMEOUT", message=str(exc)))
    except AIServiceUnavailableError as exc:
        return GenericResponse(status="error", code=503, message=str(exc), error=ErrorDetail(code="SERVICE_UNAVAILABLE", message=str(exc)))
    except Exception as exc:
        logger.error(f"[{engine.upper()}] Unexpected error in {doc_type}: {exc}", exc_info=True)
        return GenericResponse(status="error", code=500, message=f"AI OCR processing failed: {exc}", error=ErrorDetail(code="INTERNAL_ERROR", message=str(exc)))



# ── AI Endpoints ───────────────────────────────────────────────────────────

@router.post(
    "/raport",
    response_model=OCRResultResponse,
    status_code=200,
    summary="OCR AI Qwen",
    description="Upload a report card image or PDF and extract data using the Qwen Vision model.",
    tags=["OCR AI"],
)
async def ai_raport_ocr(
    file: UploadFile = File(...),
    document_store: BaseDocumentStore = Depends(get_document_store),
) -> OCRResultResponse:
    return await _handle_ai_raport_upload(file, "qwen", document_store)


@router.post(
    "/ktp",
    response_model=GenericResponse,
    status_code=200,
    summary="OCR AI Qwen",
    description="Extract KTP data using Qwen Vision model.",
    tags=["OCR AI"],
)
async def ai_ktp_ocr(file: UploadFile = File(...)) -> GenericResponse:
    return await _handle_ai_generic_upload(file, "qwen", "KTP")


@router.post(
    "/kk",
    response_model=GenericResponse,
    status_code=200,
    summary="OCR AI Qwen",
    description="Extract KK data using Qwen Vision model.",
    tags=["OCR AI"],
)
async def ai_kk_ocr(file: UploadFile = File(...)) -> GenericResponse:
    return await _handle_ai_generic_upload(file, "qwen", "KK")


@router.post(
    "/akta",
    response_model=GenericResponse,
    status_code=200,
    summary="OCR AI Qwen",
    description="Extract Akta data using Qwen Vision model.",
    tags=["OCR AI"],
)
async def ai_akta_ocr(file: UploadFile = File(...)) -> GenericResponse:
    return await _handle_ai_generic_upload(file, "qwen", "Akta")


@router.post(
    "/kp",
    response_model=GenericResponse,
    status_code=200,
    summary="OCR AI Qwen",
    description="Extract KP data using Qwen Vision model.",
    tags=["OCR AI"],
)
async def ai_kp_ocr(file: UploadFile = File(...)) -> GenericResponse:
    return await _handle_ai_generic_upload(file, "qwen", "KP")
