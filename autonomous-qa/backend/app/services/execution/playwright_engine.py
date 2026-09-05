"""Playwright implementation of ExecutionEngine. This is the primary,
default engine and does the actual browser work — no fabricated results.
"""
from __future__ import annotations

import os
import time
import uuid

from playwright.async_api import async_playwright

from app.core.logging import get_logger
from app.schemas.discovery import Locator
from app.schemas.test_case import Assertion, AssertionType
from app.services.execution.action_interpreter import (
    LocatorResolutionError,
    perform_action,
    resolve_locator,
)
from app.services.execution.assertions import evaluate_assertion
from app.services.execution.engine import (
    ExecutionEngine,
    ExecutionResult,
    HealingCallback,
    StepExecutionRecord,
    TestDefinition,
)

logger = get_logger(__name__)


class PlaywrightEngine(ExecutionEngine):
    name = "playwright"

    async def run_test(
        self,
        test_definition: TestDefinition,
        *,
        headless: bool = True,
        timeout_ms: int = 30000,
        healing_callback: HealingCallback | None = None,
        artifacts_dir: str | None = None,
    ) -> ExecutionResult:
        start = time.monotonic()
        step_results: list[StepExecutionRecord] = []
        healing_events: list[dict] = []
        console_logs: list[dict] = []
        network_failures: list[dict] = []
        screenshot_path: str | None = None
        trace_path: str | None = None
        overall_status = "PASSED"
        error_message: str | None = None
        assertion_results: list[dict] = []

        artifacts_dir = artifacts_dir or "/tmp/qa-artifacts"
        os.makedirs(artifacts_dir, exist_ok=True)
        run_token = uuid.uuid4().hex[:10]

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=headless)
            context = await browser.new_context()
            context.set_default_timeout(timeout_ms)
            await context.tracing.start(screenshots=True, snapshots=True, sources=False)
            page = await context.new_page()

            page.on(
                "console",
                lambda msg: console_logs.append({"type": msg.type, "text": msg.text[:500]}),
            )
            page.on(
                "requestfailed",
                lambda req: network_failures.append(
                    {"url": req.url, "failure": (req.failure or {}).get("errorText") if isinstance(req.failure, dict) else str(req.failure)}
                ),
            )

            try:
                if not test_definition.steps or test_definition.steps[0].action != "goto":
                    await page.goto(test_definition.base_url)

                for step in test_definition.steps:
                    record = StepExecutionRecord(order_index=step.order_index, action=step.action, status="PASSED")
                    try:
                        if step.action in ("goto", "wait", "screenshot"):
                            if step.action == "screenshot":
                                shot_path = os.path.join(artifacts_dir, f"{run_token}_step{step.order_index}.png")
                                await page.screenshot(path=shot_path)
                                record.locator_used = None
                            else:
                                await perform_action(page, step.action, None, step.value)
                        else:
                            element, used_locator, heal_event = await self._resolve_with_healing(
                                page, step, healing_callback, timeout_ms
                            )
                            if heal_event:
                                healing_events.append(heal_event)
                                record.status = "HEALED" if heal_event.get("outcome") == "HEALED" else record.status
                                record.healing_event = heal_event
                            record.locator_used = used_locator.model_dump(mode="json") if used_locator else None
                            await perform_action(page, step.action, element, step.value)
                    except LocatorResolutionError as exc:
                        record.status = "FAILED"
                        record.error = str(exc)
                        step_results.append(record)
                        overall_status = "FAILED"
                        error_message = f"Step {step.order_index} ({step.action}) failed: {exc}"
                        break
                    except Exception as exc:  # noqa: BLE001
                        record.status = "FAILED"
                        record.error = str(exc)
                        step_results.append(record)
                        overall_status = "FAILED"
                        error_message = f"Step {step.order_index} ({step.action}) raised: {exc}"
                        break
                    step_results.append(record)

                if overall_status != "FAILED":
                    for assertion_def in test_definition.assertions:
                        assertion = Assertion(
                            type=AssertionType(assertion_def.type),
                            expected_value=assertion_def.expected_value,
                            locator=assertion_def.locator,
                        )
                        result = await evaluate_assertion(page, assertion, timeout_ms)
                        assertion_results.append(result.__dict__)
                        if not result.passed:
                            overall_status = "FAILED"
                            error_message = f"Assertion failed: {result.message} (expected={result.expected!r}, actual={result.actual!r})"

                if overall_status == "FAILED":
                    screenshot_path = os.path.join(artifacts_dir, f"{run_token}_failure.png")
                    try:
                        await page.screenshot(path=screenshot_path)
                    except Exception:  # noqa: BLE001
                        screenshot_path = None
                elif any(r.status == "HEALED" for r in step_results):
                    overall_status = "HEALED"

            finally:
                trace_path = os.path.join(artifacts_dir, f"{run_token}_trace.zip")
                try:
                    await context.tracing.stop(path=trace_path)
                except Exception:  # noqa: BLE001
                    trace_path = None
                await context.close()
                await browser.close()

        duration_ms = int((time.monotonic() - start) * 1000)
        return ExecutionResult(
            status=overall_status,
            duration_ms=duration_ms,
            step_results=step_results,
            assertion_results=assertion_results,
            error_message=error_message,
            screenshot_path=screenshot_path,
            trace_path=trace_path,
            console_logs=console_logs[-50:],
            network_failures=network_failures[-50:],
            healing_events=healing_events,
        )

    async def _resolve_with_healing(self, page, step, healing_callback, timeout_ms):
        """Try the step's own locator first; only invoke the healing
        callback (deterministic-then-AI, per confidence policy) if that
        fails."""
        try:
            element = await resolve_locator(page, step.locator, timeout_ms)
            return element, step.locator, None
        except LocatorResolutionError as original_exc:
            if healing_callback is None:
                raise
            heal_result = await healing_callback(page, step)
            if not heal_result or not heal_result.get("replacement_locator"):
                raise LocatorResolutionError(
                    "Original locator failed and no healing candidate met the confidence threshold."
                ) from original_exc
            new_locator = Locator.model_validate(heal_result["replacement_locator"])
            element = await resolve_locator(page, new_locator, timeout_ms)
            return element, new_locator, heal_result
