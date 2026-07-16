from fastapi import APIRouter, UploadFile, File, BackgroundTasks

from app.parsers.kp_parser import parse_kp
from app.schemas.generic_response import GenericResponse
from app.utils.ocr_request_handler import handle_ocr_request

router = APIRouter()


@router.post("/kp", response_model=GenericResponse, tags=["OCR"])
async def ocr_kp(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):
    return await handle_ocr_request(
        file=file,
        background_tasks=background_tasks,
        parser_fn=parse_kp,
        doc_label="Kartu Pelajar",
        page_mode="first",
        success_message="Kartu Pelajar data extracted successfully",
        preprocess=True,
    )
