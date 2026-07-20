from fastapi import APIRouter, UploadFile, File, BackgroundTasks

from app.parsers.akta_parser import parse_akta
from app.schemas.generic_response import GenericResponse
from app.utils.ocr_request_handler import handle_ocr_request

router = APIRouter()


@router.post("/akta", response_model=GenericResponse, tags=["OCR"])
async def ocr_akta(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):
    return await handle_ocr_request(
        file=file,
        background_tasks=background_tasks,
        parser_fn=parse_akta,
        doc_label="Akta",
        page_mode="first",
        success_message="Akta data extracted successfully",
        preprocess=True,
    )