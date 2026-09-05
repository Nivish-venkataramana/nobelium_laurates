"""Confidence policy: turns a ranked candidate list into a healing
decision. Never silently changes a test when confidence is low."""
from __future__ import annotations

from dataclasses import dataclass

from app.core.config import get_settings
from app.services.healing.selector_ranker import ScoredCandidate


@dataclass
class HealingDecision:
    outcome: str  # HEAL | REVIEW_REQUIRED | NO_CANDIDATES
    best: ScoredCandidate | None
    threshold: float


def decide(scored_candidates: list[ScoredCandidate]) -> HealingDecision:
    settings = get_settings()
    threshold = settings.HEALING_CONFIDENCE_THRESHOLD

    if not scored_candidates:
        return HealingDecision(outcome="NO_CANDIDATES", best=None, threshold=threshold)

    best = scored_candidates[0]
    if best.confidence >= threshold:
        return HealingDecision(outcome="HEAL", best=best, threshold=threshold)
    return HealingDecision(outcome="REVIEW_REQUIRED", best=best, threshold=threshold)
