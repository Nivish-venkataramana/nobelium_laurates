from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TestResultOut(BaseModel):
    id: str
    test_run_id: str
    test_case_id: str
    status: str
    engine: str
    browser: str
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_ms: int | None = None
    step_results: list
    error_message: str | None = None
    screenshot_path: str | None = None
    trace_path: str | None = None
    risk_score: float | None = None
    risk_level: str | None = None
    ai_explanation: str | None = None

    model_config = ConfigDict(from_attributes=True)
