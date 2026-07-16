"""
app/worker/celery_app.py
=========================
Celery application factory.

Only active when REDIS_URL is configured. If Redis is not configured,
the worker module is still importable but tasks won't be dispatched.
"""

from __future__ import annotations

import os

from celery import Celery

from app.core.config import settings

# Fall back to a dummy broker URL so the module is always importable,
# even when Redis is not configured (in-memory store mode).
_broker_url = settings.redis_url or "memory://"
_backend_url = settings.redis_url or "cache+memory://"

celery_app = Celery(
    "ocr_worker",
    broker=_broker_url,
    backend=_backend_url,
    include=["app.worker.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    worker_concurrency=int(os.getenv("CELERY_CONCURRENCY", "2")),
    task_track_started=True,
    task_time_limit=3600,  # 1 hour max
)
