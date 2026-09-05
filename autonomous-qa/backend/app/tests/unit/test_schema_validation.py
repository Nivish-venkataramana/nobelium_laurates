import pytest
from pydantic import ValidationError

from app.schemas.test_case import TestPlanResponse


def _valid_test(steps, assertions=None):
    return {
        "application_id": "app1",
        "tests": [
            {
                "id": "TC001",
                "name": "Login",
                "business_intent": "USER_LOGIN",
                "category": "FUNCTIONAL",
                "priority": "HIGH",
                "risk": "HIGH",
                "steps": steps,
                "assertions": assertions
                or [{"type": "visible", "target_element_id": "el_1"}],
                "expected": "User reaches dashboard",
                "rationale": "Critical workflow",
            }
        ],
    }


def test_valid_plan_passes():
    plan = _valid_test(
        steps=[
            {
                "order_index": 0,
                "action": "click",
                "target_element_id": "el_1",
                "locator": {"primary": {"strategy": "testid", "value": "login-button"}},
            }
        ]
    )
    validated = TestPlanResponse.model_validate(plan)
    assert validated.tests[0].id == "TC001"


def test_unsupported_action_is_rejected():
    plan = _valid_test(steps=[{"order_index": 0, "action": "exec_shell", "value": "ls"}])
    with pytest.raises(ValidationError):
        TestPlanResponse.model_validate(plan)


def test_code_injection_in_value_is_rejected():
    plan = _valid_test(
        steps=[
            {
                "order_index": 0,
                "action": "fill",
                "target_element_id": "el_1",
                "locator": {"primary": {"strategy": "testid", "value": "x"}},
                "value": "__import__('os').system('rm -rf /')",
            }
        ]
    )
    with pytest.raises(ValidationError):
        TestPlanResponse.model_validate(plan)


def test_click_action_requires_locator():
    plan = _valid_test(steps=[{"order_index": 0, "action": "click", "target_element_id": "el_1"}])
    with pytest.raises(ValidationError):
        TestPlanResponse.model_validate(plan)


def test_duplicate_order_index_is_rejected():
    plan = _valid_test(
        steps=[
            {"order_index": 0, "action": "goto", "value": "https://example.com"},
            {"order_index": 0, "action": "wait", "value": "1000"},
        ]
    )
    with pytest.raises(ValidationError):
        TestPlanResponse.model_validate(plan)
