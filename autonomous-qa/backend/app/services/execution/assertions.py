"""Deterministic assertion evaluation. Assertions are what actually
decide PASS/FAIL for a step — never the AI."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.schemas.test_case import Assertion
from app.services.execution.action_interpreter import resolve_locator


@dataclass
class AssertionResult:
    type: str
    passed: bool
    expected: str | None
    actual: str | None
    message: str


async def evaluate_assertion(page: Any, assertion: Assertion, timeout_ms: int = 5000) -> AssertionResult:
    try:
        if assertion.type.value == "url":
            actual = page.url
            passed = assertion.expected_value is not None and assertion.expected_value in actual
            return AssertionResult("url", passed, assertion.expected_value, actual, "URL assertion")

        if assertion.locator is None:
            return AssertionResult(
                assertion.type.value, False, assertion.expected_value, None,
                "Assertion requires a locator but none was provided.",
            )

        element = await resolve_locator(page, assertion.locator, timeout_ms)

        if assertion.type.value == "visible":
            passed = await element.is_visible()
            return AssertionResult("visible", passed, "visible", str(passed), "Visibility assertion")

        if assertion.type.value == "hidden":
            passed = not await element.is_visible()
            return AssertionResult("hidden", passed, "hidden", str(not passed), "Hidden assertion")

        if assertion.type.value == "text":
            actual = (await element.inner_text()).strip()
            expected = assertion.expected_value or ""
            passed = expected.lower() in actual.lower()
            return AssertionResult("text", passed, expected, actual, "Text assertion")

        if assertion.type.value == "value":
            actual = await element.input_value()
            expected = assertion.expected_value or ""
            passed = actual == expected
            return AssertionResult("value", passed, expected, actual, "Value assertion")

        if assertion.type.value == "attribute":
            actual = await element.get_attribute(assertion.expected_value or "")
            passed = actual is not None
            return AssertionResult("attribute", passed, assertion.expected_value, actual, "Attribute assertion")

        if assertion.type.value == "count":
            count = await element.count()
            expected = int(assertion.expected_value or 0)
            passed = count == expected
            return AssertionResult("count", passed, str(expected), str(count), "Count assertion")

        return AssertionResult(assertion.type.value, False, None, None, "Unsupported assertion type")
    except Exception as exc:  # noqa: BLE001
        return AssertionResult(assertion.type.value, False, assertion.expected_value, None, str(exc))
