"""ExecutionEngine abstraction.

TestDefinition -> ExecutionEngine -> ExecutionResult

Playwright is the default/primary implementation; Selenium implements
the same interface so the same TestDefinition can theoretically run on
either engine without any business-logic duplication.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from app.schemas.discovery import Locator


@dataclass
class TestStepDefinition:
    order_index: int
    action: str
    target_element_id: str | None
    locator: Locator | None
    value: str | None
    description: str | None = None


@dataclass
class AssertionDefinition:
    type: str
    expected_value: str | None
    locator: Locator | None


@dataclass
class TestDefinition:
    test_case_id: str
    name: str
    steps: list[TestStepDefinition]
    assertions: list[AssertionDefinition]
    base_url: str


@dataclass
class StepExecutionRecord:
    order_index: int
    action: str
    status: str  # PASSED | FAILED | HEALED
    locator_used: dict | None = None
    error: str | None = None
    healing_event: dict | None = None


@dataclass
class ExecutionResult:
    status: str  # PASSED | FAILED | HEALED | HEALING_FAILED | REVIEW_REQUIRED | ERROR
    duration_ms: int
    step_results: list[StepExecutionRecord] = field(default_factory=list)
    assertion_results: list[dict] = field(default_factory=list)
    error_message: str | None = None
    screenshot_path: str | None = None
    trace_path: str | None = None
    console_logs: list[dict] = field(default_factory=list)
    network_failures: list[dict] = field(default_factory=list)
    healing_events: list[dict] = field(default_factory=list)


# Called when a step's locator fails to resolve. Given the page, the
# failed step, and current DOM candidates, may return a repaired
# Locator (already independently verified) or None if healing did not
# succeed. Kept as an injectable callback so the execution engine does
# not need to import the healing service directly (keeps layers decoupled
# and testable in isolation).
HealingCallback = Callable[[Any, TestStepDefinition], Awaitable[dict | None]]


class ExecutionEngine(ABC):
    name: str = "abstract"

    @abstractmethod
    async def run_test(
        self,
        test_definition: TestDefinition,
        *,
        headless: bool = True,
        timeout_ms: int = 30000,
        healing_callback: HealingCallback | None = None,
        artifacts_dir: str | None = None,
    ) -> ExecutionResult:
        raise NotImplementedError
