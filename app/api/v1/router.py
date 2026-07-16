"""
app/api/v1/router.py
=====================
APIRouter for API version 1 — PaddleOCR branch (dev-paddle).

Single endpoint: POST /api/v1/ocr/paddle
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.endpoints.ocr import router as ocr_router
from app.routes.ktp_route import router as ktp_router
from app.routes.kk_route import router as kk_router
from app.routes.akta_route import router as akta_router
from app.routes.kp_route import router as kp_router

router = APIRouter(prefix="/api/v1/ocr")
router.include_router(ocr_router)
router.include_router(ktp_router)
router.include_router(kk_router)
router.include_router(akta_router)
router.include_router(kp_router)

combined_router = router


