"""
app/api/v1/router.py
=====================
APIRouter untuk API versi 1.

Endpoints:
  POST /api/v1/ocr/paddle                    — Upload + proses OCR PaddleOCR
  GET  /api/v1/ocr/paddle/debug/{documentId} — Raw OCR debug output
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.endpoints.ocr import router as ocr_router

router = APIRouter(prefix="/api/v1/ocr")
router.include_router(ocr_router)
