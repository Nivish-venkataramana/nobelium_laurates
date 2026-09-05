"""Self-healing orchestrator.

Order of operations (cost-controlled, per spec section 28):
  1. primary locator (already tried by the caller before this runs)
  2. fallback locators (already tried by resolve_locator before this runs)
  3. deterministic semantic matching against current DOM candidates
  4. candidate ranking / confidence scoring
  5. LLM-assisted analysis, ONLY if deterministic ranking is inconclusive

The LLM never applies a repair itself. Its recommendation is looked up
in the same deterministically-scored candidate list and independently
re-checked before it is used.
"""
from __future__ import annotations

from datetime import UTC
from typing import Any

from app.core.config import get_settings
from app.core.logging import get_logger
from app.schemas.discovery import ElementModel, Locator
from app.services.ai.json_extract import extract_json_object
from app.services.ai.prompts import HEALING_SYSTEM_PROMPT, build_healing_task_prompt
from app.services.ai.provider import LLMProvider
from app.services.execution.engine import TestStepDefinition
from app.services.healing.candidate_finder import find_candidates
from app.services.healing.confidence import decide
from app.services.healing.selector_ranker import ScoredCandidate, rank_candidates

logger = get_logger(__name__)

# Deterministic confidence below this is not even worth showing to the
# AI as "plausible" context — avoids wasting a call on garbage candidates.
_AI_FALLBACK_MIN_TOP_SCORE = 0.35


def _pseudo_original_element(step: TestStepDefinition) -> ElementModel:
    """Reconstruct a comparable ElementModel from the failed step's own
    locator metadata (we don't always have the full original snapshot
    element on hand at execution time, but the locator + description
    carry the same identifying signals)."""
    primary = step.locator.primary if step.locator else None
    text_hint = None
    role_hint = None
    if primary:
        if primary.strategy == "role":
            text_hint = primary.name
            role_hint = primary.role
        elif primary.value:
            text_hint = primary.value
    if not text_hint and step.description:
        text_hint = step.description

    return ElementModel(
        id="original",
        tag=role_hint or "button",
        role=role_hint,
        text=text_hint,
        aria_label=text_hint,
        page_url="",
        locators=Locator(primary=primary or {"strategy": "text", "value": text_hint or ""}),
    )


async def heal_step(
    page: Any,
    step: TestStepDefinition,
    *,
    ai_provider: LLMProvider | None = None,
    db=None,
    test_run_id: str | None = None,
) -> dict:
    """Attempt to heal a single failed step. Returns a dict describing
    the outcome; never raises for a failed/inconclusive heal (the caller
    decides what to do with REVIEW_REQUIRED)."""
    settings = get_settings()
    original = _pseudo_original_element(step)

    candidates = await find_candidates(page)
    scored = rank_candidates(original, candidates)
    decision = decide(scored)

    candidates_considered = [
        {
            "element_id": s.candidate.element.id,
            "text": s.candidate.element.text,
            "confidence": round(s.confidence, 3),
            "breakdown": s.breakdown,
        }
        for s in scored[:10]
    ]

    if decision.outcome == "HEAL" and decision.best is not None:
        return {
            "outcome": "HEALED",
            "method": "deterministic",
            "confidence": decision.best.confidence,
            "reason": (
                f"Deterministic matching found a high-confidence candidate "
                f"(text={decision.best.candidate.element.text!r}) exceeding the "
                f"{decision.threshold:.2f} confidence threshold."
            ),
            "replacement_locator": decision.best.candidate.element.locators.model_dump(mode="json"),
            "candidates_considered": candidates_considered,
        }

    if decision.outcome == "NO_CANDIDATES":
        return {
            "outcome": "REVIEW_REQUIRED",
            "method": "deterministic",
            "confidence": 0.0,
            "reason": "No interactive elements were found in the current DOM to consider as replacements.",
            "replacement_locator": None,
            "candidates_considered": [],
        }

    # Deterministic ranking was inconclusive — optionally escalate to the
    # LLM, but only if there's at least a plausible candidate to reason
    # about, to avoid burning AI calls on hopeless cases.
    top_score = scored[0].confidence if scored else 0.0
    if (
        settings.HEALING_LLM_FALLBACK_ENABLED
        and ai_provider is not None
        and top_score >= _AI_FALLBACK_MIN_TOP_SCORE
    ):
        ai_pick = await _ask_ai_for_candidate(
            ai_provider, original, scored, db=db, test_run_id=test_run_id
        )
        if ai_pick is not None:
            return ai_pick

    return {
        "outcome": "REVIEW_REQUIRED",
        "method": "deterministic",
        "confidence": top_score,
        "reason": (
            f"The best deterministic candidate scored {top_score:.2f}, below the "
            f"{decision.threshold:.2f} confidence threshold required for automatic repair."
        ),
        "replacement_locator": None,
        "candidates_considered": candidates_considered,
    }


async def _ask_ai_for_candidate(
    ai_provider: LLMProvider,
    original: ElementModel,
    scored: list[ScoredCandidate],
    *,
    db=None,
    test_run_id: str | None = None,
) -> dict | None:
    from datetime import datetime

    from app.models.ai_request import AIRequest

    context = {
        "original_element": {"text": original.text, "role": original.role, "tag": original.tag},
        "candidates": [
            {
                "id": s.candidate.element.id,
                "tag": s.candidate.element.tag,
                "role": s.candidate.element.role,
                "text": s.candidate.element.text,
                "aria_label": s.candidate.element.aria_label,
                "deterministic_confidence": round(s.confidence, 3),
            }
            for s in scored[:8]
        ],
    }

    system_prompt = HEALING_SYSTEM_PROMPT
    task_prompt = build_healing_task_prompt(context)
    requested_at = datetime.now(UTC)

    try:
        result = await ai_provider.suggest_healing(
            context=context, system_prompt=system_prompt, task_prompt=task_prompt
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("healer.ai_call_failed", error=str(exc))
        return None

    if db is not None:
        db.add(
            AIRequest(
                test_run_id=test_run_id,
                operation="suggest_healing",
                provider=ai_provider.name,
                model=result.model,
                prompt_summary=task_prompt[:500],
                raw_response={"text": result.raw_text[:2000]},
                prompt_tokens=result.prompt_tokens,
                completion_tokens=result.completion_tokens,
                estimated_cost_usd=result.estimated_cost_usd,
                latency_ms=result.latency_ms,
                requested_at=requested_at,
            )
        )
        db.commit()

    try:
        parsed = extract_json_object(result.raw_text)
    except Exception:  # noqa: BLE001
        return None

    picked_id = parsed.get("candidate_element_id")
    if not picked_id:
        return None

    # Independent validation: the AI's pick must be one of the actual
    # candidates we already deterministically scored, and that candidate's
    # OWN deterministic score is what we trust — not the AI's self-reported
    # confidence — before ever repairing anything.
    matched = next((s for s in scored if s.candidate.element.id == picked_id), None)
    if matched is None:
        logger.warning("healer.ai_picked_unknown_candidate", picked_id=picked_id)
        return None

    settings = get_settings()
    candidates_considered = [
        {
            "element_id": s.candidate.element.id,
            "text": s.candidate.element.text,
            "confidence": round(s.confidence, 3),
            "breakdown": s.breakdown,
        }
        for s in scored[:10]
    ]

    if matched.confidence >= settings.HEALING_CONFIDENCE_THRESHOLD * 0.9:
        # Slightly relaxed threshold for AI-assisted confirmations, since
        # the AI's semantic judgement is corroborating a candidate that
        # deterministic scoring already found plausible — but we still
        # require it to clear a high, independently-computed bar.
        return {
            "outcome": "HEALED",
            "method": "ai_assisted",
            "confidence": matched.confidence,
            "reason": (
                f"AI recommended this candidate ({parsed.get('reason', '')}); "
                f"independently verified at deterministic confidence {matched.confidence:.2f}."
            ),
            "replacement_locator": matched.candidate.element.locators.model_dump(mode="json"),
            "candidates_considered": candidates_considered,
        }

    return {
        "outcome": "REVIEW_REQUIRED",
        "method": "ai_assisted",
        "confidence": matched.confidence,
        "reason": (
            f"AI suggested a candidate, but its independently-computed "
            f"confidence ({matched.confidence:.2f}) did not clear the bar "
            "required for automatic repair."
        ),
        "replacement_locator": None,
        "candidates_considered": candidates_considered,
    }
