"""
app/api/v1/endpoints/minicpm_route.py
======================================
HTTP handlers for MiniCPM AI Vision OCR endpoints.

Endpoints:
  POST /api/v1/ocr/minicpm/raport
  POST /api/v1/ocr/minicpm/ktp
  POST /api/v1/ocr/minicpm/kk
  POST /api/v1/ocr/minicpm/akta
  POST /api/v1/ocr/minicpm/kp

All endpoints accept multipart/form-data with a single 'file' field.
Supported formats: PDF, PNG, JPG, JPEG.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile

from app.api.deps import get_document_store
from app.infrastructure.storage.base import BaseDocumentStore
from app.schemas.ocr_schemas import OCRResultResponse
from app.schemas.generic_response import GenericResponse
from app.api.v1.endpoints.ai_route import _handle_ai_raport_upload, _handle_ai_generic_upload

router = APIRouter(prefix="/minicpm")


# ── AI Endpoints (MiniCPM) ────────────────────────────────────────────────

@router.post(
    "/raport",
    response_model=OCRResultResponse,
    status_code=200,
    summary="OCR AI MiniCPM",
    description="Upload a report card image or PDF and extract data using the MiniCPM Vision model.",
    tags=["OCR MiniCPM"],
)
async def minicpm_raport_ocr(
    file: UploadFile = File(...),
    document_store: BaseDocumentStore = Depends(get_document_store),
) -> OCRResultResponse:
    return await _handle_ai_raport_upload(file, "minicpm", document_store)


@router.post(
    "/ktp",
    response_model=GenericResponse,
    status_code=200,
    summary="OCR AI MiniCPM",
    description="Extract KTP data using MiniCPM Vision model.",
    tags=["OCR MiniCPM"],
)
async def minicpm_ktp_ocr(file: UploadFile = File(...)) -> GenericResponse:
    return await _handle_ai_generic_upload(file, "minicpm", "KTP")


@router.post(
    "/kk",
    response_model=GenericResponse,
    status_code=200,
    summary="OCR AI MiniCPM",
    description="Extract KK data using MiniCPM Vision model.",
    tags=["OCR MiniCPM"],
)
async def minicpm_kk_ocr(file: UploadFile = File(...)) -> GenericResponse:
    return await _handle_ai_generic_upload(file, "minicpm", "KK")


@router.post(
    "/akta",
    response_model=GenericResponse,
    status_code=200,
    summary="OCR AI MiniCPM",
    description="Extract Akta data using MiniCPM Vision model.",
    tags=["OCR MiniCPM"],
)
async def minicpm_akta_ocr(file: UploadFile = File(...)) -> GenericResponse:
    return await _handle_ai_generic_upload(file, "minicpm", "Akta")


@router.post(
    "/kp",
    response_model=GenericResponse,
    status_code=200,
    summary="OCR AI MiniCPM",
    description="Extract KP data using MiniCPM Vision model.",
    tags=["OCR MiniCPM"],
)
async def minicpm_kp_ocr(file: UploadFile = File(...)) -> GenericResponse:
    return await _handle_ai_generic_upload(file, "minicpm", "KP")
