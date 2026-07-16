from fastapi import APIRouter, UploadFile, File, BackgroundTasks

from app.parsers.ktp_parser import parse_ktp
from app.schemas.generic_response import GenericResponse
from app.utils.ocr_request_handler import handle_ocr_request

router = APIRouter()


@router.post("/ktp", response_model=GenericResponse, tags=["OCR"])
async def ocr_ktp(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):
    return await handle_ocr_request(
        file=file,
        background_tasks=background_tasks,
        parser_fn=parse_ktp,
        doc_label="KTP",
        page_mode="first",
        success_message="KTP data extracted successfully",
        preprocess=True,
    )