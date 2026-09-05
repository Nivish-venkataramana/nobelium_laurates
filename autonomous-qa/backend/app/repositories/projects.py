from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.models.project import Project


def create(db: Session, *, name: str, description: str | None) -> Project:
    project = Project(name=name, description=description)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def list_all(db: Session) -> list[Project]:
    return db.query(Project).order_by(Project.created_at.desc()).all()


def get(db: Session, project_id: str) -> Project | None:
    return db.query(Project).filter(Project.id == uuid.UUID(project_id)).first()
