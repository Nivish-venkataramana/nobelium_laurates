from __future__ import annotations

import uuid

from sqlalchemy.orm import Session, joinedload

from app.models.test_result import TestResult
from app.models.test_run import RunStatus, TestRun


def create(
    db: Session,
    *,
    application_id: str,
    trigger: str,
    run_discovery: bool,
    run_generation: bool,
    max_tests: int,
    timeout_seconds: int,
    single_test_case_id: str | None = None,
) -> TestRun:
    run = TestRun(
        application_id=uuid.UUID(application_id),
        trigger=trigger,
        run_discovery=run_discovery,
        run_generation=run_generation,
        max_tests=max_tests,
        timeout_seconds=timeout_seconds,
        status=RunStatus.CREATED,
        single_test_case_id=uuid.UUID(single_test_case_id) if single_test_case_id else None,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def get(db: Session, run_id: str) -> TestRun | None:
    return db.query(TestRun).filter(TestRun.id == uuid.UUID(run_id)).first()


def list_all(db: Session, application_id: str | None = None, limit: int = 50) -> list[TestRun]:
    q = db.query(TestRun)
    if application_id:
        q = q.filter(TestRun.application_id == uuid.UUID(application_id))
    return q.order_by(TestRun.created_at.desc()).limit(limit).all()


def list_results(db: Session, run_id: str) -> list[TestResult]:
    return (
        db.query(TestResult)
        .options(joinedload(TestResult.test_case))
        .filter(TestResult.test_run_id == uuid.UUID(run_id))
        .order_by(TestResult.created_at)
        .all()
    )
