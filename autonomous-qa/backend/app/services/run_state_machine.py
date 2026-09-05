"""Enforces the TestRun state machine's allowed transitions. Every
status change in the orchestrator must go through this function so an
invalid transition raises immediately instead of silently corrupting
run state."""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.models.test_run import ALLOWED_TRANSITIONS, RunStatus, TestRun


class InvalidTransitionError(AppError):
    http_status = 409
    safe_message = "Invalid test run state transition."


def transition(db: Session, run: TestRun, new_status: RunStatus, *, commit: bool = True) -> TestRun:
    current = run.status if isinstance(run.status, RunStatus) else RunStatus(run.status)
    allowed = ALLOWED_TRANSITIONS.get(current, set())
    if new_status not in allowed and new_status != current:
        raise InvalidTransitionError(f"Cannot transition run from {current} to {new_status}.")

    run.status = new_status
    if new_status == RunStatus.EXECUTING and run.started_at is None:
        run.started_at = datetime.now(UTC)
    if new_status in (RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED):
        run.finished_at = datetime.now(UTC)

    if commit:
        db.add(run)
        db.commit()
        db.refresh(run)
    return run
