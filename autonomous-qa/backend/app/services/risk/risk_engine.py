"""Transparent, explainable risk scoring.

Every input is a real, observable signal (never an opaque black-box
score). The output is one of LOW/MEDIUM/HIGH/CRITICAL plus the full
numeric breakdown so the frontend can show exactly why a risk level was
assigned.
"""
from __future__ import annotations

from dataclasses import dataclass, field

_CRITICALITY_WEIGHT = 0.25
_CHANGE_MAGNITUDE_WEIGHT = 0.20
_HISTORICAL_FAILURE_WEIGHT = 0.20
_SECURITY_SENSITIVITY_WEIGHT = 0.20
_REGRESSION_HISTORY_WEIGHT = 0.15

_BUSINESS_CRITICAL_INTENTS = {
    "USER_LOGIN",
    "PRODUCT_PURCHASE",
    "PASSWORD_RESET",
    "USER_REGISTRATION",
}
_SECURITY_SENSITIVE_INTENTS = {"USER_LOGIN", "PASSWORD_RESET", "USER_REGISTRATION"}


@dataclass
class RiskInputs:
    business_intent: str
    change_magnitude: float  # 0-1, e.g. fraction of test's elements affected
    historical_failure_rate: float  # 0-1, from past N runs of this test
    security_sensitive_override: bool = False
    regression_break_count: int = 0  # times this test has broken due to UI changes historically


@dataclass
class RiskScore:
    level: str  # LOW | MEDIUM | HIGH | CRITICAL
    score: float  # 0-1
    breakdown: dict = field(default_factory=dict)


def _business_criticality(intent: str) -> float:
    return 1.0 if intent.upper() in _BUSINESS_CRITICAL_INTENTS else 0.4


def _security_sensitivity(intent: str, override: bool) -> float:
    if override:
        return 1.0
    return 1.0 if intent.upper() in _SECURITY_SENSITIVE_INTENTS else 0.1


def _regression_history_score(break_count: int) -> float:
    # Diminishing returns: 0 breaks -> 0.0, 1 -> 0.4, 2 -> 0.65, 3+ -> 0.85-1.0
    if break_count <= 0:
        return 0.0
    if break_count == 1:
        return 0.4
    if break_count == 2:
        return 0.65
    return min(1.0, 0.65 + 0.1 * (break_count - 2))


def compute_risk(inputs: RiskInputs) -> RiskScore:
    criticality = _business_criticality(inputs.business_intent)
    magnitude = max(0.0, min(1.0, inputs.change_magnitude))
    failure_rate = max(0.0, min(1.0, inputs.historical_failure_rate))
    security = _security_sensitivity(inputs.business_intent, inputs.security_sensitive_override)
    regression = _regression_history_score(inputs.regression_break_count)

    score = (
        criticality * _CRITICALITY_WEIGHT
        + magnitude * _CHANGE_MAGNITUDE_WEIGHT
        + failure_rate * _HISTORICAL_FAILURE_WEIGHT
        + security * _SECURITY_SENSITIVITY_WEIGHT
        + regression * _REGRESSION_HISTORY_WEIGHT
    )
    score = max(0.0, min(1.0, score))

    if score >= 0.75:
        level = "CRITICAL"
    elif score >= 0.55:
        level = "HIGH"
    elif score >= 0.3:
        level = "MEDIUM"
    else:
        level = "LOW"

    breakdown = {
        "business_criticality": {"value": round(criticality, 3), "weight": _CRITICALITY_WEIGHT},
        "change_magnitude": {"value": round(magnitude, 3), "weight": _CHANGE_MAGNITUDE_WEIGHT},
        "historical_failure_rate": {"value": round(failure_rate, 3), "weight": _HISTORICAL_FAILURE_WEIGHT},
        "security_sensitivity": {"value": round(security, 3), "weight": _SECURITY_SENSITIVITY_WEIGHT},
        "regression_history": {"value": round(regression, 3), "weight": _REGRESSION_HISTORY_WEIGHT},
        "total_score": round(score, 3),
    }
    return RiskScore(level=level, score=score, breakdown=breakdown)


def prioritize_tests(risk_scores: dict[str, RiskScore]) -> list[str]:
    """Return test_case_ids ordered highest-risk-first."""
    return [
        tid
        for tid, _ in sorted(risk_scores.items(), key=lambda kv: kv[1].score, reverse=True)
    ]
