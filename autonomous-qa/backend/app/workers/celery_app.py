"""Celery application instance. Test execution must never block HTTP
request threads — the API enqueues a run and returns immediately with
{"run_id": ..., "status": "QUEUED"}; this worker process executes it."""
from __future__ import annotations

from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "autonomous_qa",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_soft_time_limit=settings.RUN_TIMEOUT_SECONDS,
    task_time_limit=settings.RUN_TIMEOUT_SECONDS + 60,
)

# Ensure task modules are registered.
celery_app.autodiscover_tasks(["app.workers"])
