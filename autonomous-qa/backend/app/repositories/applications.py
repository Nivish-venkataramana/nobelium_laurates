from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.models.application import Application


def create(db: Session, *, project_id: str, name: str, base_url: str, browser_engine: str) -> Application:
    app_row = Application(
        project_id=uuid.UUID(project_id), name=name, base_url=base_url, browser_engine=browser_engine
    )
    db.add(app_row)
    db.commit()
    db.refresh(app_row)
    return app_row


def list_all(db: Session, project_id: str | None = None) -> list[Application]:
    q = db.query(Application)
    if project_id:
        q = q.filter(Application.project_id == uuid.UUID(project_id))
    return q.order_by(Application.created_at.desc()).all()


def get(db: Session, application_id: str) -> Application | None:
    return db.query(Application).filter(Application.id == uuid.UUID(application_id)).first()
