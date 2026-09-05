from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.core.exceptions import SecurityValidationError
from app.core.security import validate_target_url
from app.repositories import applications as applications_repo
from app.schemas.application import ApplicationCreate, ApplicationOut

router = APIRouter(prefix="/api/applications", tags=["applications"])


def _to_out(a) -> ApplicationOut:
    return ApplicationOut(
        id=str(a.id),
        project_id=str(a.project_id),
        name=a.name,
        base_url=a.base_url,
        browser_engine=a.browser_engine,
        created_at=a.created_at,
    )


@router.post("", response_model=ApplicationOut, status_code=201)
def create_application(payload: ApplicationCreate, db: Session = Depends(get_db)) -> ApplicationOut:
    try:
        validate_target_url(str(payload.base_url))
    except SecurityValidationError as exc:
        raise HTTPException(status_code=400, detail=exc.detail) from exc

    app_row = applications_repo.create(
        db,
        project_id=payload.project_id,
        name=payload.name,
        base_url=str(payload.base_url),
        browser_engine=payload.browser_engine,
    )
    return _to_out(app_row)


@router.get("", response_model=list[ApplicationOut])
def list_applications(project_id: str | None = None, db: Session = Depends(get_db)) -> list[ApplicationOut]:
    return [_to_out(a) for a in applications_repo.list_all(db, project_id=project_id)]


@router.get("/{application_id}", response_model=ApplicationOut)
def get_application(application_id: str, db: Session = Depends(get_db)) -> ApplicationOut:
    app_row = applications_repo.get(db, application_id)
    if app_row is None:
        raise HTTPException(status_code=404, detail="Application not found.")
    return _to_out(app_row)
