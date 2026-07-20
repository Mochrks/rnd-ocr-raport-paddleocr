from fastapi import APIRouter, UploadFile, File, BackgroundTasks

from app.services.parsers.kk_parser import parse_kk
from app.schemas.generic_response import GenericResponse
from app.utils.ocr_request_handler import handle_ocr_request

router = APIRouter()


@router.post("/kk", response_model=GenericResponse, tags=["OCR Paddle"], summary="OCR Engine Paddle")
async def ocr_kk(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):
    return await handle_ocr_request(
        file=file,
        background_tasks=background_tasks,
        parser_fn=parse_kk,
        doc_label="KK",
        page_mode="all",
        success_message="KK data extracted successfully",
        preprocess=True,
    )
