"""
app/api/v1/router.py
=====================
APIRouter for API version 1 — PaddleOCR branch (dev-paddle).

Single endpoint: POST /api/v1/ocr/paddle
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.endpoints.ocr import router as ocr_router

router = APIRouter(prefix="/api/v1/ocr")
router.include_router(ocr_router)
