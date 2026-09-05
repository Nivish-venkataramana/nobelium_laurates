from app.services.risk.risk_engine import RiskInputs, compute_risk, prioritize_tests


def test_login_workflow_with_changes_and_history_is_critical():
    risk = compute_risk(
        RiskInputs(
            business_intent="USER_LOGIN",
            change_magnitude=1.0,
            historical_failure_rate=0.4,
            regression_break_count=2,
        )
    )
    assert risk.level == "CRITICAL"
    assert 0.0 <= risk.score <= 1.0


def test_low_criticality_workflow_with_no_history_is_low():
    risk = compute_risk(
        RiskInputs(
            business_intent="PRODUCT_SEARCH",
            change_magnitude=0.0,
            historical_failure_rate=0.0,
            regression_break_count=0,
        )
    )
    assert risk.level == "LOW"


def test_breakdown_sums_to_reported_total_score():
    risk = compute_risk(
        RiskInputs(
            business_intent="PASSWORD_RESET",
            change_magnitude=0.5,
            historical_failure_rate=0.2,
            regression_break_count=1,
        )
    )
    weighted_sum = sum(v["value"] * v["weight"] for k, v in risk.breakdown.items() if k != "total_score")
    assert abs(weighted_sum - risk.breakdown["total_score"]) < 0.01


def test_prioritize_tests_orders_highest_risk_first():
    scores = {
        "low": compute_risk(RiskInputs(business_intent="X", change_magnitude=0.0, historical_failure_rate=0.0)),
        "high": compute_risk(
            RiskInputs(business_intent="USER_LOGIN", change_magnitude=1.0, historical_failure_rate=0.8, regression_break_count=3)
        ),
    }
    ordered = prioritize_tests(scores)
    assert ordered[0] == "high"
