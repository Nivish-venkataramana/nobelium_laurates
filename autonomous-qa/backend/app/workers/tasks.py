"""Celery task definitions.

Each task owns its own DB session (never reuses a request-scoped
session) and wraps the async orchestrator with asyncio.run, since
Celery workers are synchronous by default. Any unhandled exception is
caught here so a run can never get stuck in a non-terminal state.
"""
from __future__ import annotations

import asyncio

from app.core.logging import configure_logging, get_logger
from app.db.database import SessionLocal
from app.models.test_run import RunStatus
from app.services.execution.orchestrator import run_pipeline
from app.services.run_state_machine import transition
from app.workers.celery_app import celery_app

configure_logging()
logger = get_logger(__name__)


@celery_app.task(name="app.workers.tasks.execute_test_run", bind=True, max_retries=0)
def execute_test_run(self, run_id: str) -> None:
    db = SessionLocal()
    try:
        from app.repositories.runs import get as get_run

        run = get_run(db, run_id)
        if run is None:
            logger.error("tasks.run_not_found", run_id=run_id)
            return

        if run.status == RunStatus.CREATED:
            transition(db, run, RunStatus.QUEUED)

        try:
            asyncio.run(run_pipeline(db, run))
        except Exception as exc:  # noqa: BLE001
            logger.error("tasks.run_failed", run_id=run_id, error=str(exc))
            db.rollback()
            run = get_run(db, run_id)
            if run and run.status not in (RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED):
                run.status = RunStatus.FAILED
                run.error_message = str(exc)[:2000]
                db.add(run)
                db.commit()
    finally:
        db.close()
