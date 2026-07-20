import os
import shutil
import logging
import time
from typing import Callable
from fastapi import UploadFile, BackgroundTasks
from app.utils.file_validator import validate_upload_file
from app.services.ocr_service import extract_boxes_from_file
from app.services.preprocess.image_preprocess import preprocess_image
from app.schemas.generic_response import GenericResponse, ErrorDetail
logger = logging.getLogger(__name__)
UPLOADS_DIR = "uploads"
def _cleanup_files(*paths: str) -> None:
    for path in paths:
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except OSError as e:
                logger.warning(f"Gagal menghapus file {path}: {e}")
async def handle_ocr_request(
    file: UploadFile,
    background_tasks: BackgroundTasks,
    parser_fn: Callable,
    doc_label: str,
    page_mode: str = "first",
    success_message: str | None = None,
    preprocess: bool = True,
) -> GenericResponse:
    file_location = None
    try:
        os.makedirs(UPLOADS_DIR, exist_ok=True)
        validation_error = await validate_upload_file(file)
        if validation_error:
            return validation_error
        ext = os.path.splitext(file.filename)[1].lower()
        file_location = os.path.join(UPLOADS_DIR, file.filename)
        with open(file_location, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        background_tasks.add_task(_cleanup_files, file_location)
        ocr_start = time.time()
        if ext != ".pdf" and preprocess:
            image_array = preprocess_image(file_location)
            boxes = extract_boxes_from_file(image_array, page_mode=page_mode)
        else:
            boxes = extract_boxes_from_file(file_location, page_mode=page_mode)
        ocr_elapsed = time.time() - ocr_start
        if not boxes:
            return GenericResponse(
                status="error",
                code=422,
                message="No text detected in file",
                error=ErrorDetail(
                    code="NO_TEXT_DETECTED",
                    message="OCR could not extract any text from the file",
                ),
            )
        confidences = [box["confidence"] for box in boxes if "confidence" in box]
        accuracy = round(
            (sum(confidences) / len(confidences)) * 100 if confidences else 0.0,
            2,
        )
        result = parser_fn(boxes)
        msg = success_message or f"{doc_label} data extracted successfully"
        return GenericResponse(
            status="success",
            code=200,
            message=msg,
            data=result,
            raw_text=boxes,
            accuracy_percentage=accuracy,
            elapsed_time=round(ocr_elapsed, 3),
        )
    except FileNotFoundError as e:
        logger.error(f"[{doc_label}] File not found: {e}")
        return GenericResponse(
            status="error",
            code=404,
            message="File not found",
            error=ErrorDetail(
                code="FILE_NOT_FOUND",
                message=str(e),
            ),
        )
    except Exception as e:
        logger.error(f"[{doc_label}] Error processing: {e}", exc_info=True)
        return GenericResponse(
            status="error",
            code=500,
            message="Internal server error",
            error=ErrorDetail(
                code="INTERNAL_ERROR",
                message=str(e),
            ),
        )
