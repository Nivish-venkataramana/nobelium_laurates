"""Deterministic candidate scoring for self-healing.

Weights (sum to 1.0, matching the product spec):
    role match           +0.25
    text similarity      +0.25
    semantic similarity  +0.20
    structure            +0.15
    attributes           +0.15

Every signal is computed from real, observable properties of the
original element and the candidate — nothing here is a black box.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from rapidfuzz import fuzz

from app.schemas.discovery import ElementModel
from app.services.healing.candidate_finder import HealingCandidate

# Small, explicit synonym groups covering common UI relabeling patterns.
# This is what lets the engine recognize "Login" ~ "Sign In" without
# calling the LLM for every routine rename.
_SYNONYM_GROUPS: list[set[str]] = [
    {"login", "log in", "sign in", "signin"},
    {"logout", "log out", "sign out", "signout"},
    {"register", "sign up", "signup", "create account", "join"},
    {"submit", "continue", "proceed", "next", "confirm"},
    {"delete", "remove", "trash"},
    {"edit", "modify", "update", "change"},
    {"search", "find", "look up"},
    {"add to cart", "add to bag", "add item"},
    {"checkout", "buy now", "purchase", "place order"},
    {"cancel", "dismiss", "close"},
    {"save", "apply", "done"},
]


def _normalize(text: str | None) -> str:
    return (text or "").strip().lower()


def _semantic_similarity(a: str | None, b: str | None) -> float:
    a_norm, b_norm = _normalize(a), _normalize(b)
    if not a_norm or not b_norm:
        return 0.0
    if a_norm == b_norm:
        return 1.0
    for group in _SYNONYM_GROUPS:
        if a_norm in group and b_norm in group:
            return 1.0
        # partial containment against a synonym group member
        for member in group:
            if a_norm in group and member in b_norm:
                return 0.85
            if b_norm in group and member in a_norm:
                return 0.85
    # fall back to token-level fuzzy match as a weak semantic signal
    return fuzz.token_sort_ratio(a_norm, b_norm) / 100.0 * 0.6


def _known_synonym_pair(a_norm: str, b_norm: str) -> bool:
    return any(a_norm in group and b_norm in group for group in _SYNONYM_GROUPS)


def _text_similarity(a: str | None, b: str | None) -> float:
    """Character-level similarity, with a floor applied when the two
    labels are a well-known UI synonym pair (e.g. "Login"/"Sign In").
    Pure edit-distance would score such pairs very low even though a
    human tester would immediately recognize them as the same control —
    this keeps the deterministic signal aligned with that judgement
    instead of relying on the semantic-similarity signal alone to carry
    the whole case."""
    a_norm, b_norm = _normalize(a), _normalize(b)
    if not a_norm or not b_norm:
        return 0.0
    char_ratio = fuzz.ratio(a_norm, b_norm) / 100.0
    if _known_synonym_pair(a_norm, b_norm):
        return max(char_ratio, 0.9)
    return char_ratio


def _role_match(original: ElementModel, candidate: ElementModel) -> float:
    if original.role and candidate.role and original.role == candidate.role:
        return 1.0
    if original.tag == candidate.tag:
        return 0.6
    return 0.0


def _structure_match(original: ElementModel, candidate: ElementModel) -> float:
    score = 0.0
    if original.tag == candidate.tag:
        score += 0.6
    if original.input_type and candidate.input_type and original.input_type == candidate.input_type:
        score += 0.4
    elif original.tag in ("button", "a") and candidate.tag in ("button", "a"):
        score += 0.2
    return min(score, 1.0)


def _attribute_match(original: ElementModel, candidate: ElementModel) -> float:
    score = 0.0
    total = 0
    for attr in ("name", "placeholder", "test_id"):
        original_val = getattr(original, attr)
        candidate_val = getattr(candidate, attr)
        if original_val or candidate_val:
            total += 1
            if original_val and candidate_val and original_val == candidate_val:
                score += 1
    if total == 0:
        # No comparable attributes; neutral score rather than 0 to avoid
        # unfairly penalizing elements that simply don't carry any of
        # these optional attributes (common for plain <button> labels).
        return 0.4
    return score / total


@dataclass
class ScoredCandidate:
    candidate: HealingCandidate
    confidence: float
    breakdown: dict = field(default_factory=dict)


def score_candidate(original: ElementModel, candidate: HealingCandidate) -> ScoredCandidate:
    c = candidate.element
    role_score = _role_match(original, c)
    text_score = _text_similarity(original.text, c.text) if original.text else _text_similarity(
        original.aria_label, c.aria_label
    )
    semantic_score = _semantic_similarity(
        original.text or original.aria_label, c.text or c.aria_label
    )
    structure_score = _structure_match(original, c)
    attribute_score = _attribute_match(original, c)

    confidence = (
        role_score * 0.25
        + text_score * 0.25
        + semantic_score * 0.20
        + structure_score * 0.15
        + attribute_score * 0.15
    )
    confidence = max(0.0, min(1.0, confidence))

    breakdown = {
        "role_match": round(role_score, 3),
        "text_similarity": round(text_score, 3),
        "semantic_similarity": round(semantic_score, 3),
        "structure": round(structure_score, 3),
        "attributes": round(attribute_score, 3),
        "weights": {
            "role_match": 0.25,
            "text_similarity": 0.25,
            "semantic_similarity": 0.20,
            "structure": 0.15,
            "attributes": 0.15,
        },
    }
    return ScoredCandidate(candidate=candidate, confidence=confidence, breakdown=breakdown)


def rank_candidates(
    original: ElementModel, candidates: list[HealingCandidate]
) -> list[ScoredCandidate]:
    scored = [score_candidate(original, c) for c in candidates]
    return sorted(scored, key=lambda s: s.confidence, reverse=True)
