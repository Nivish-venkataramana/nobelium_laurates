from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class HealingCandidateOut(BaseModel):
    element_id: str
    locator: dict
    confidence: float
    score_breakdown: dict
    text: str | None = None


class HealingEventOut(BaseModel):
    id: str
    test_run_id: str
    test_case_id: str
    original_locator: dict
    replacement_locator: dict | None = None
    candidates_considered: list
    confidence: float
    method: str
    reason: str
    outcome: str
    verification_result: str | None = None
    healed_at: datetime | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
