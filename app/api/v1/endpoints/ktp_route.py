from fastapi import APIRouter, UploadFile, File, BackgroundTasks

from app.services.parsers.ktp_parser import parse_ktp
from app.schemas.generic_response import GenericResponse
from app.utils.ocr_request_handler import handle_ocr_request
from app.infrastructure.data.db_client import get_use_ai_ocr_flag
from app.api.v1.endpoints.ai_route import _handle_ai_generic_upload

router = APIRouter()


@router.post("/ktp", response_model=GenericResponse, tags=["OCR Paddle"], summary="OCR Engine Paddle")
async def ocr_ktp(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):
    use_ai = await get_use_ai_ocr_flag()
    if use_ai:
        return await _handle_ai_generic_upload(file, "qwen", "KTP")

    return await handle_ocr_request(
        file=file,
        background_tasks=background_tasks,
        parser_fn=parse_ktp,
        doc_label="KTP",
        page_mode="first",
        success_message="KTP data extracted successfully",
        preprocess=True,
    )
