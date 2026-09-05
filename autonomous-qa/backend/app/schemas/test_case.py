"""Pydantic schemas for AI-generated test plans.

This is the enforcement point for the platform's core safety rule: the
LLM may only ever produce data structures drawn from a fixed allowlist
of actions and assertions. Anything else fails validation and is
rejected before it ever reaches an execution engine.
"""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.discovery import Locator


class ActionType(str, Enum):
    GOTO = "goto"
    CLICK = "click"
    FILL = "fill"
    TYPE = "type"
    SELECT = "select"
    CHECK = "check"
    UNCHECK = "uncheck"
    HOVER = "hover"
    PRESS = "press"
    WAIT = "wait"
    SCREENSHOT = "screenshot"


class AssertionType(str, Enum):
    VISIBLE = "visible"
    HIDDEN = "hidden"
    TEXT = "text"
    URL = "url"
    VALUE = "value"
    ATTRIBUTE = "attribute"
    COUNT = "count"


ALLOWED_ACTIONS = {a.value for a in ActionType}
ALLOWED_ASSERTIONS = {a.value for a in AssertionType}

# Actions that require a target locator (goto/wait/screenshot do not).
ACTIONS_REQUIRING_LOCATOR = {
    ActionType.CLICK,
    ActionType.FILL,
    ActionType.TYPE,
    ActionType.SELECT,
    ActionType.CHECK,
    ActionType.UNCHECK,
    ActionType.HOVER,
}

# Patterns that indicate an attempt to smuggle code/shell execution through
# a text field. Defense-in-depth on top of the schema-level allowlist.
_FORBIDDEN_VALUE_PATTERNS = (
    "import os",
    "subprocess",
    "eval(",
    "exec(",
    "<script",
    "javascript:",
    "os.system",
    "rm -rf",
    "curl ",
    "wget ",
    "; sh",
    "&& sh",
    "__import__",
)


class Assertion(BaseModel):
    type: AssertionType
    target_element_id: str | None = None
    expected_value: str | None = None
    locator: Locator | None = None

    @field_validator("expected_value")
    @classmethod
    def no_code_injection(cls, v: str | None) -> str | None:
        if v:
            lowered = v.lower()
            for pattern in _FORBIDDEN_VALUE_PATTERNS:
                if pattern in lowered:
                    raise ValueError(f"Value contains a forbidden pattern: {pattern!r}")
        return v


class TestStepPlan(BaseModel):
    order_index: int
    action: ActionType
    target_element_id: str | None = None
    locator: Locator | None = None
    value: str | None = None
    description: str | None = None

    @field_validator("value")
    @classmethod
    def no_code_injection(cls, v: str | None) -> str | None:
        if v:
            lowered = v.lower()
            for pattern in _FORBIDDEN_VALUE_PATTERNS:
                if pattern in lowered:
                    raise ValueError(f"Value contains a forbidden pattern: {pattern!r}")
        return v

    @field_validator("locator")
    @classmethod
    def locator_required_for_targeted_actions(cls, v, info):
        action = info.data.get("action")
        if action in ACTIONS_REQUIRING_LOCATOR and v is None:
            raise ValueError(f"Action '{action}' requires a locator.")
        return v

    @model_validator(mode="after")
    def check_locator_present_for_targeted_actions(self) -> TestStepPlan:
        # A separate model-level check on top of the field_validator above.
        # Pydantic v2 skips field_validator on fields that fall back to
        # their default (locator defaults to None), so relying on the
        # field_validator alone would silently accept a targeted action
        # with a completely omitted locator. This always runs.
        if self.action in ACTIONS_REQUIRING_LOCATOR and self.locator is None:
            raise ValueError(f"Action '{self.action}' requires a locator.")
        return self

class TestCategory(str, Enum):
    SMOKE = "SMOKE"
    FUNCTIONAL = "FUNCTIONAL"
    NEGATIVE = "NEGATIVE"
    VALIDATION = "VALIDATION"
    BOUNDARY = "BOUNDARY"
    NAVIGATION = "NAVIGATION"
    WORKFLOW = "WORKFLOW"
    REGRESSION = "REGRESSION"


class Priority(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class TestCasePlan(BaseModel):
    """A single AI-proposed test case. Must pass full validation before
    it is persisted or ever reaches the execution engine."""

    id: str = Field(description="Human-readable code, e.g. TC001")
    name: str
    business_intent: str
    category: TestCategory
    priority: Priority
    risk: RiskLevel
    steps: list[TestStepPlan] = Field(min_length=1)
    assertions: list[Assertion] = Field(min_length=1)
    expected: str
    rationale: str

    @field_validator("steps")
    @classmethod
    def steps_ordered_and_allowlisted(cls, v: list[TestStepPlan]) -> list[TestStepPlan]:
        seen_orders = set()
        for step in v:
            if step.action.value not in ALLOWED_ACTIONS:
                raise ValueError(f"Action '{step.action}' is not in the allowlist.")
            if step.order_index in seen_orders:
                raise ValueError("Duplicate step order_index detected.")
            seen_orders.add(step.order_index)
        return sorted(v, key=lambda s: s.order_index)


class TestPlanResponse(BaseModel):
    """The full validated output of AI test planning for one application."""

    application_id: str
    tests: list[TestCasePlan]


class TestCaseOut(BaseModel):
    id: str
    external_code: str
    name: str
    business_intent: str
    category: str
    priority: str
    risk: str
    expected_outcome: str
    rationale: str
    is_active: bool

    model_config = ConfigDict(from_attributes=True)
