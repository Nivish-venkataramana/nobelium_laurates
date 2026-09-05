from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.core.config import get_settings
from app.models.test_run import RunStatus
from app.repositories import applications as applications_repo
from app.repositories import runs as runs_repo
from app.schemas.test_run import TestRunCreate, TestRunOut
from app.services.run_state_machine import transition
from app.workers.tasks import execute_test_run

router = APIRouter(prefix="/api/runs", tags=["runs"])


def _to_out(run) -> TestRunOut:
    return TestRunOut(
        id=str(run.id),
        application_id=str(run.application_id),
        status=run.status.value if hasattr(run.status, "value") else run.status,
        trigger=run.trigger,
        started_at=run.started_at,
        finished_at=run.finished_at,
        tests_generated=run.tests_generated,
        tests_executed=run.tests_executed,
        tests_passed=run.tests_passed,
        tests_failed=run.tests_failed,
        tests_healed=run.tests_healed,
        tests_review_required=run.tests_review_required,
        quality_score=run.quality_score,
        quality_score_breakdown=run.quality_score_breakdown,
        ai_explanation=run.ai_explanation,
        error_message=run.error_message,
        created_at=run.created_at,
    )


@router.post("", response_model=TestRunOut, status_code=202)
def create_run(payload: TestRunCreate, db: Session = Depends(get_db)) -> TestRunOut:
    application = applications_repo.get(db, payload.application_id)
    if application is None:
        raise HTTPException(status_code=404, detail="Application not found.")

    settings = get_settings()
    run = runs_repo.create(
        db,
        application_id=payload.application_id,
        trigger=payload.trigger,
        run_discovery=payload.run_discovery,
        run_generation=payload.run_generation,
        max_tests=min(payload.max_tests, settings.MAX_TESTS_PER_RUN),
        timeout_seconds=settings.RUN_TIMEOUT_SECONDS,
    )
    transition(db, run, RunStatus.QUEUED)
    execute_test_run.delay(str(run.id))
    return _to_out(run)


@router.get("", response_model=list[TestRunOut])
def list_runs(application_id: str | None = None, db: Session = Depends(get_db)) -> list[TestRunOut]:
    return [_to_out(r) for r in runs_repo.list_all(db, application_id=application_id)]


@router.get("/{run_id}", response_model=TestRunOut)
def get_run(run_id: str, db: Session = Depends(get_db)) -> TestRunOut:
    run = runs_repo.get(db, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found.")
    return _to_out(run)


@router.post("/{run_id}/cancel", response_model=TestRunOut)
def cancel_run(run_id: str, db: Session = Depends(get_db)) -> TestRunOut:
    run = runs_repo.get(db, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found.")
    if run.status in (RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED):
        raise HTTPException(status_code=409, detail=f"Cannot cancel a run in status {run.status}.")
    transition(db, run, RunStatus.CANCELLED)
    return _to_out(run)


@router.post("/{run_id}/rerun", response_model=TestRunOut, status_code=202)
def rerun(run_id: str, db: Session = Depends(get_db)) -> TestRunOut:
    original = runs_repo.get(db, run_id)
    if original is None:
        raise HTTPException(status_code=404, detail="Run not found.")

    settings = get_settings()
    new_run = runs_repo.create(
        db,
        application_id=str(original.application_id),
        trigger="rerun",
        run_discovery=original.run_discovery,
        run_generation=original.run_generation,
        max_tests=original.max_tests,
        timeout_seconds=settings.RUN_TIMEOUT_SECONDS,
        single_test_case_id=str(original.single_test_case_id) if original.single_test_case_id else None,
    )
    transition(db, new_run, RunStatus.QUEUED)
    execute_test_run.delay(str(new_run.id))
    return _to_out(new_run)
