from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TestRunCreate(BaseModel):
    application_id: str
    run_discovery: bool = True
    run_generation: bool = True
    max_tests: int = Field(default=25, ge=1, le=100)
    trigger: str = Field(default="manual")


class TestRunOut(BaseModel):
    id: str
    application_id: str
    status: str
    trigger: str
    started_at: datetime | None = None
    finished_at: datetime | None = None
    tests_generated: int
    tests_executed: int
    tests_passed: int
    tests_failed: int
    tests_healed: int
    tests_review_required: int
    quality_score: int | None = None
    quality_score_breakdown: dict | None = None
    ai_explanation: dict | None = None
    error_message: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
