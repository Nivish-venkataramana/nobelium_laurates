from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.repositories import projects as projects_repo
from app.schemas.project import ProjectCreate, ProjectOut

router = APIRouter(prefix="/api/projects", tags=["projects"])


def _to_out(p) -> ProjectOut:
    return ProjectOut(id=str(p.id), name=p.name, description=p.description, created_at=p.created_at)


@router.post("", response_model=ProjectOut, status_code=201)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)) -> ProjectOut:
    project = projects_repo.create(db, name=payload.name, description=payload.description)
    return _to_out(project)


@router.get("", response_model=list[ProjectOut])
def list_projects(db: Session = Depends(get_db)) -> list[ProjectOut]:
    return [_to_out(p) for p in projects_repo.list_all(db)]


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project_id: str, db: Session = Depends(get_db)) -> ProjectOut:
    project = projects_repo.get(db, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    return _to_out(project)
