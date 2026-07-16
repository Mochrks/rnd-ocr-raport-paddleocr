"""
app/api/v1/router.py
=====================
APIRouter for API version 1. Registers all v1 endpoint routers.

Adding a new feature to v1? Just import its router here and add
a single include_router() call — no other file needs to change.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.endpoints.ocr import router as ocr_router
from app.api.v1.endpoints.ai_ocr import router as ai_ocr_router

# Legacy PaddleOCR routes — original path preserved for backward compatibility
# POST /api/v1/academic/report/upload
# GET  /api/v1/academic/report/status/{documentId}
# GET  /api/v1/academic/report/{documentId}/debug
router = APIRouter(prefix="/api/v1/academic")
router.include_router(ocr_router)

# Unified OCR routes — all engines under /api/v1/ocr/<engine>
# POST /api/v1/ocr/paddle    — PaddleOCR local engine
# POST /api/v1/ocr/deepseek  — DeepSeek Vision (→ qwen3-vl:8b)
# POST /api/v1/ocr/qwen      — Qwen3-VL Vision
ai_router = APIRouter(prefix="/api/v1/ocr")
ai_router.include_router(ai_ocr_router)

# Combine into a single exported router
combined_router = APIRouter()
combined_router.include_router(router)
combined_router.include_router(ai_router)
