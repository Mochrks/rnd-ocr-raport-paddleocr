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

# All v1 routes share the /api/v1/academic prefix
router = APIRouter(prefix="/api/v1/academic")

router.include_router(ocr_router)
