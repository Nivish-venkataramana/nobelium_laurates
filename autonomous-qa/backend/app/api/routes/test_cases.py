from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.core.config import get_settings
from app.models.test_run import RunStatus
from app.repositories import runs as runs_repo
from app.repositories import test_cases as test_cases_repo
from app.schemas.test_case import TestCaseOut
from app.schemas.test_run import TestRunOut
from app.services.run_state_machine import transition
from app.workers.tasks import execute_test_run

router = APIRouter(prefix="/api/tests", tags=["test_cases"])


def _to_out(tc) -> TestCaseOut:
    return TestCaseOut(
        id=str(tc.id),
        external_code=tc.external_code,
        name=tc.name,
        business_intent=tc.business_intent,
        category=tc.category,
        priority=tc.priority,
        risk=tc.risk,
        expected_outcome=tc.expected_outcome,
        rationale=tc.rationale,
        is_active=tc.is_active,
    )


@router.get("", response_model=list[TestCaseOut])
def list_tests(application_id: str, db: Session = Depends(get_db)) -> list[TestCaseOut]:
    return [_to_out(tc) for tc in test_cases_repo.list_for_application(db, application_id)]


@router.get("/{test_id}")
def get_test(test_id: str, db: Session = Depends(get_db)) -> dict:
    tc = test_cases_repo.get(db, test_id)
    if tc is None:
        raise HTTPException(status_code=404, detail="Test case not found.")
    return {
        **_to_out(tc).model_dump(),
        "steps": [
            {
                "order_index": s.order_index,
                "action": s.action,
                "target_element_id": s.target_element_id,
                "locator": s.locator,
                "value": s.value,
                "description": s.description,
            }
            for s in sorted(tc.steps, key=lambda x: x.order_index)
        ],
        "assertions": tc.assertions,
    }


@router.post("/{test_id}/run", response_model=TestRunOut, status_code=202)
def run_single_test(test_id: str, db: Session = Depends(get_db)) -> TestRunOut:
    tc = test_cases_repo.get(db, test_id)
    if tc is None:
        raise HTTPException(status_code=404, detail="Test case not found.")

    settings = get_settings()
    run = runs_repo.create(
        db,
        application_id=str(tc.application_id),
        trigger="manual",
        run_discovery=False,
        run_generation=False,
        max_tests=1,
        timeout_seconds=settings.RUN_TIMEOUT_SECONDS,
        single_test_case_id=test_id,
    )
    transition(db, run, RunStatus.QUEUED)
    execute_test_run.delay(str(run.id))
    return TestRunOut(
        id=str(run.id),
        application_id=str(run.application_id),
        status=run.status.value,
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
