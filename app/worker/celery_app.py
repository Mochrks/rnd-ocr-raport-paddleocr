import os

from celery import Celery

from app.core.config import settings

# Initialize Celery app
celery_app = Celery(
    "ocr_worker",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.worker.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Worker concurrency is usually set via command line, e.g., --concurrency=2
    # but we limit it here by default to prevent overloading PaddleOCR
    worker_concurrency=int(os.getenv("CELERY_CONCURRENCY", 2)),
    task_track_started=True,
    task_time_limit=3600, # 1 hour max
)
