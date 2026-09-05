"""Shared FastAPI dependencies: DB session, request-id propagation, and
a minimal API-key auth gate (kept intentionally simple; a full
identity provider integration is out of scope for this platform core
but the dependency injection seam is here for one to be added)."""
from __future__ import annotations

from collections.abc import Generator

from fastapi import Header, HTTPException
from sqlalchemy.orm import Session

from app.db.database import SessionLocal


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def verify_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """No-op unless API_KEY is set in the environment, so local/demo use
    works out of the box while production deployments can require a key
    by setting one."""
    import os

    configured_key = os.environ.get("API_KEY")
    if not configured_key:
        return
    if x_api_key != configured_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key.")
