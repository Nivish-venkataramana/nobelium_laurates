"""Public entry point for AI-driven test generation.

Kept as a distinct module from test_planner so that callers (API routes,
Celery tasks) have one obvious import, while test_planner.py owns the
validation pipeline. Currently a thin re-export; the split makes it easy
to insert generation-only steps (e.g. deduping against existing test
cases) without touching the validation pipeline.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.test_case import TestCase
from app.schemas.discovery import ApplicationModel
from app.services.ai.provider import LLMProvider
from app.services.ai.test_planner import generate_test_plan


async def generate_and_persist_tests(
    db: Session,
    *,
    provider: LLMProvider,
    application_id: str,
    application_model: ApplicationModel,
    max_tests: int,
    test_run_id: str | None = None,
) -> list[TestCase]:
    return await generate_test_plan(
        db,
        provider=provider,
        application_id=application_id,
        application_model=application_model,
        max_tests=max_tests,
        test_run_id=test_run_id,
    )
