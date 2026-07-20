from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.endpoints.raport_route import router as ocr_router
from app.api.v1.endpoints.ktp_route import router as ktp_router
from app.api.v1.endpoints.kk_route import router as kk_router
from app.api.v1.endpoints.akta_route import router as akta_router
from app.api.v1.endpoints.kp_route import router as kp_route
from app.api.v1.endpoints.ai_route import router as ai_route

router = APIRouter(prefix="/api/v1/ocr")
router.include_router(ocr_router)
router.include_router(ktp_router)
router.include_router(kk_router)
router.include_router(akta_router)
router.include_router(kp_route)
router.include_router(ai_route)

combined_router = router


