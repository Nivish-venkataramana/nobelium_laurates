from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.core.exceptions import DiscoveryError, SecurityValidationError
from app.core.security import validate_target_url
from app.models.snapshot import ApplicationSnapshot
from app.repositories import applications as applications_repo
from app.schemas.discovery import DiscoveryRequest, DiscoveryResponse
from app.services.discovery.crawler import discover_application

router = APIRouter(prefix="/api/discovery", tags=["discovery"])


@router.post("", response_model=DiscoveryResponse)
async def run_discovery(payload: DiscoveryRequest, db: Session = Depends(get_db)) -> DiscoveryResponse:
    application = applications_repo.get(db, payload.application_id)
    if application is None:
        raise HTTPException(status_code=404, detail="Application not found.")

    try:
        validate_target_url(str(payload.url))
        application_model = await discover_application(str(payload.url), max_pages=payload.max_pages)
    except SecurityValidationError as exc:
        raise HTTPException(status_code=400, detail=exc.detail) from exc
    except DiscoveryError as exc:
        raise HTTPException(status_code=422, detail=exc.detail) from exc

    prev = (
        db.query(ApplicationSnapshot)
        .filter(ApplicationSnapshot.application_id == application.id)
        .order_by(ApplicationSnapshot.sequence_number.desc())
        .first()
    )
    next_seq = (prev.sequence_number + 1) if prev else 1

    snapshot = ApplicationSnapshot(
        application_id=application.id,
        sequence_number=next_seq,
        root_url=str(payload.url),
        title=application_model.application.title,
        application_model=application_model.model_dump(mode="json"),
        element_count=len(application_model.elements),
        page_count=len(application_model.pages),
    )
    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)

    return DiscoveryResponse(
        snapshot_id=str(snapshot.id),
        application_model=application_model,
        element_count=snapshot.element_count,
        page_count=snapshot.page_count,
    )
