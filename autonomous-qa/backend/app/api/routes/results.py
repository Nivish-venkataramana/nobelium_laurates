from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.models.healing_event import HealingEvent
from app.repositories import runs as runs_repo
from app.schemas.healing import HealingEventOut
from app.schemas.result import TestResultOut

router = APIRouter(prefix="/api", tags=["results"])


@router.get("/runs/{run_id}/results", response_model=list[TestResultOut])
def get_run_results(run_id: str, db: Session = Depends(get_db)) -> list[TestResultOut]:
    run = runs_repo.get(db, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found.")
    results = runs_repo.list_results(db, run_id)
    return [
        TestResultOut(
            id=str(r.id),
            test_run_id=str(r.test_run_id),
            test_case_id=str(r.test_case_id),
            status=r.status,
            engine=r.engine,
            browser=r.browser,
            started_at=r.started_at,
            finished_at=r.finished_at,
            duration_ms=r.duration_ms,
            step_results=r.step_results,
            error_message=r.error_message,
            screenshot_path=r.screenshot_path,
            trace_path=r.trace_path,
            risk_score=r.risk_score,
            risk_level=r.risk_level,
            ai_explanation=r.ai_explanation,
        )
        for r in results
    ]


@router.get("/healing-events", response_model=list[HealingEventOut])
def list_healing_events(
    run_id: str | None = None, test_case_id: str | None = None, db: Session = Depends(get_db)
) -> list[HealingEventOut]:
    q = db.query(HealingEvent)
    if run_id:
        q = q.filter(HealingEvent.test_run_id == run_id)
    if test_case_id:
        q = q.filter(HealingEvent.test_case_id == test_case_id)
    events = q.order_by(HealingEvent.created_at.desc()).limit(200).all()
    return [
        HealingEventOut(
            id=str(e.id),
            test_run_id=str(e.test_run_id),
            test_case_id=str(e.test_case_id),
            original_locator=e.original_locator,
            replacement_locator=e.replacement_locator,
            candidates_considered=e.candidates_considered,
            confidence=e.confidence,
            method=e.method,
            reason=e.reason,
            outcome=e.outcome,
            verification_result=e.verification_result,
            healed_at=e.healed_at,
            created_at=e.created_at,
        )
        for e in events
    ]
