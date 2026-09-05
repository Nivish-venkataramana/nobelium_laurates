from __future__ import annotations

import uuid

from sqlalchemy.orm import Session, joinedload

from app.models.test_case import TestCase


def list_for_application(db: Session, application_id: str) -> list[TestCase]:
    return (
        db.query(TestCase)
        .options(joinedload(TestCase.steps))
        .filter(TestCase.application_id == uuid.UUID(application_id), TestCase.is_active.is_(True))
        .order_by(TestCase.external_code)
        .all()
    )


def get(db: Session, test_case_id: str) -> TestCase | None:
    return (
        db.query(TestCase)
        .options(joinedload(TestCase.steps), joinedload(TestCase.results))
        .filter(TestCase.id == uuid.UUID(test_case_id))
        .first()
    )


def list_all(db: Session) -> list[TestCase]:
    return db.query(TestCase).filter(TestCase.is_active.is_(True)).all()
