"""Turns raw execution failure evidence into a plain-language, evidence-
grounded explanation. The AI only explains; it never decides pass/fail
(that was already determined by the execution engine before this runs).
"""
from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.orm import Session

from app.core.exceptions import AIProviderError
from app.core.logging import get_logger
from app.models.ai_request import AIRequest
from app.services.ai.json_extract import extract_json_object
from app.services.ai.prompts import (
    FAILURE_ANALYZER_SYSTEM_PROMPT,
    build_failure_analysis_task_prompt,
)
from app.services.ai.provider import LLMProvider

logger = get_logger(__name__)


class FailureAnalysis(BaseModel):
    explanation: str
    likely_cause: str = Field(pattern="^(UI_CHANGE|DATA_ISSUE|TIMING|APP_BUG|UNKNOWN)$")
    confidence: float = Field(ge=0.0, le=1.0)


async def analyze_failure(
    db: Session,
    *,
    provider: LLMProvider,
    context: dict,
    test_run_id: str | None = None,
) -> FailureAnalysis:
    system_prompt = FAILURE_ANALYZER_SYSTEM_PROMPT
    task_prompt = build_failure_analysis_task_prompt(context)

    requested_at = datetime.now(UTC)
    try:
        result = await provider.analyze_failure(
            context=context, system_prompt=system_prompt, task_prompt=task_prompt
        )
    except AIProviderError as exc:
        logger.warning("failure_analyzer.provider_error", error=str(exc))
        return FailureAnalysis(
            explanation="Automated explanation unavailable; the AI provider did not respond.",
            likely_cause="UNKNOWN",
            confidence=0.0,
        )

    ai_request = AIRequest(
        test_run_id=test_run_id,
        operation="analyze_failure",
        provider=provider.name,
        model=result.model,
        prompt_summary=task_prompt[:500],
        raw_response={"text": result.raw_text[:5000]},
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
        estimated_cost_usd=result.estimated_cost_usd,
        latency_ms=result.latency_ms,
        requested_at=requested_at,
    )

    try:
        parsed = extract_json_object(result.raw_text)
        analysis = FailureAnalysis.model_validate(parsed)
    except (ValidationError, Exception) as exc:  # noqa: BLE001
        ai_request.succeeded = False
        ai_request.error_message = str(exc)[:2000]
        db.add(ai_request)
        db.commit()
        return FailureAnalysis(
            explanation="Automated explanation unavailable; the AI response could not be parsed.",
            likely_cause="UNKNOWN",
            confidence=0.0,
        )

    db.add(ai_request)
    db.commit()
    return analysis
