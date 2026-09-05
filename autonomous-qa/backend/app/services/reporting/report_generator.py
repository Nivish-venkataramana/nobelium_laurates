"""Quality score computation and evidence-based AI explanation assembly.

The score is built entirely from real database facts (pass rate,
healing outcomes, critical failures). Dimensions with no supporting
data are marked N/A rather than guessed.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class QualityScoreResult:
    score: int  # 0-100, or -1 if not computable
    factors: dict = field(default_factory=dict)


def compute_quality_score(
    *,
    tests_executed: int,
    tests_passed: int,
    tests_healed: int,
    tests_failed: int,
    critical_failures: int,
    high_risk_executed: int,
    high_risk_passed: int,
    healing_confidences: list[float],
) -> QualityScoreResult:
    if tests_executed == 0:
        return QualityScoreResult(score=-1, factors={"note": "No tests executed yet."})

    overall_pass_rate = (tests_passed + tests_healed) / tests_executed
    high_risk_pass_rate = (
        high_risk_passed / high_risk_executed if high_risk_executed > 0 else None
    )
    healing_confidence_avg = (
        sum(healing_confidences) / len(healing_confidences) if healing_confidences else None
    )

    # Weighted composite. Only dimensions with real data contribute;
    # unavailable dimensions are displayed as N/A and excluded from the
    # weighted average (re-normalized over available weights).
    components: list[tuple[str, float | None, float]] = [
        ("high_risk_pass_rate", high_risk_pass_rate, 0.35),
        ("overall_pass_rate", overall_pass_rate, 0.30),
        ("healing_confidence", healing_confidence_avg, 0.15),
        ("accessibility", None, 0.10),  # not yet implemented — always N/A
        ("api_health", None, 0.10),  # not yet implemented — always N/A
    ]

    available = [(name, val, weight) for name, val, weight in components if val is not None]
    total_weight = sum(w for _, _, w in available) or 1.0
    weighted_sum = sum(val * w for _, val, w in available)
    base_score = (weighted_sum / total_weight) * 100

    # Critical failures apply a direct penalty regardless of the weighted
    # average — a critical break should visibly tank the score.
    penalty = min(40, critical_failures * 15)
    final_score = max(0, round(base_score - penalty))

    factors = {
        "high_risk_pass_rate": f"{high_risk_pass_rate * 100:.0f}%" if high_risk_pass_rate is not None else "N/A",
        "regression_stability": f"{overall_pass_rate * 100:.0f}%",
        "accessibility": "N/A",
        "api_health": "N/A",
        "critical_failures": critical_failures,
        "healing_confidence": (
            f"{healing_confidence_avg * 100:.0f}%" if healing_confidence_avg is not None else "N/A"
        ),
    }
    return QualityScoreResult(score=final_score, factors=factors)


def build_run_explanation(
    *,
    change_summary: str,
    impacted_count: int,
    passed: int,
    failed: int,
    healed: int,
    review_required: int,
    failure_details: list[str],
) -> dict:
    """Assemble a structured, evidence-based explanation, per section 24
    of the spec. Every sentence is derived directly from run facts."""
    lines: list[str] = []
    if change_summary and change_summary != "No UI changes detected.":
        lines.append(change_summary)
    if impacted_count:
        lines.append(f"{impacted_count} test(s) were identified as potentially impacted.")

    lines.append(f"{passed} passed.")
    if failed:
        lines.append(f"{failed} failed.")
    if healed:
        lines.append(f"{healed} test(s) required and received automatic self-healing.")
    if review_required:
        lines.append(
            f"{review_required} test(s) require manual review because no healing "
            "candidate exceeded the confidence threshold."
        )
    for detail in failure_details[:5]:
        lines.append(detail)

    return {"summary_lines": lines}
