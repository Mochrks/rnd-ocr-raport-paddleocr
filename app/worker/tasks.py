import logging

from app.application.ocr_use_case import run_ocr_pipeline
from app.worker.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="app.worker.tasks.process_ocr_task", bind=True)
def process_ocr_task(self, document_id: str, image_path: str):
    """
    Celery task that executes the OCR pipeline in the background.
    """
    logger.info(f"Starting Celery task for document: {document_id}")
    try:
        run_ocr_pipeline(document_id, image_path)
    except Exception as exc:
        logger.error(f"Task failed for document {document_id}: {exc}")
        raise
