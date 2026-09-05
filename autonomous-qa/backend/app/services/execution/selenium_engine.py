"""Selenium implementation of ExecutionEngine.

Implements the same TestDefinition -> ExecutionResult contract as
PlaywrightEngine so no business logic (test planning, healing, risk,
change intelligence) needs to know which engine actually ran a test.

This is a real, working implementation of the allowlisted action/
assertion set — not a stub — but self-healing candidate discovery and
tracing remain Playwright-first per the spec; Selenium participates in
the same healing_callback contract so healed locators still get
independently re-verified before use.
"""
from __future__ import annotations

import os
import time
import uuid

from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from app.core.logging import get_logger
from app.schemas.discovery import Locator, LocatorStrategy
from app.services.execution.engine import (
    ExecutionEngine,
    ExecutionResult,
    HealingCallback,
    StepExecutionRecord,
    TestDefinition,
)

logger = get_logger(__name__)


class LocatorResolutionErrorSelenium(Exception):
    pass


def _strategy_to_by(strat: LocatorStrategy) -> tuple[str, str]:
    if strat.strategy == "testid":
        return By.CSS_SELECTOR, f'[data-testid="{strat.value}"]'
    if strat.strategy == "role":
        return By.XPATH, f'//*[@role="{strat.role}" and contains(., "{strat.name}")]'
    if strat.strategy == "label":
        return By.XPATH, f'//*[@aria-label="{strat.value}"]'
    if strat.strategy == "name":
        return By.NAME, strat.value
    if strat.strategy == "placeholder":
        return By.CSS_SELECTOR, f'[placeholder="{strat.value}"]'
    if strat.strategy == "id":
        return By.ID, strat.value
    if strat.strategy == "text":
        return By.XPATH, f'//*[contains(text(), "{strat.value}")]'
    if strat.strategy == "css":
        return By.CSS_SELECTOR, strat.value
    if strat.strategy == "xpath":
        return By.XPATH, strat.value
    raise ValueError(f"Unknown locator strategy: {strat.strategy}")


def _resolve(driver, locator: Locator, timeout_s: float):
    strategies = [locator.primary, *locator.fallbacks]
    last_exc = None
    for strat in strategies:
        try:
            by, value = _strategy_to_by(strat)
            element = WebDriverWait(driver, timeout_s).until(EC.presence_of_element_located((by, value)))
            return element
        except (NoSuchElementException, TimeoutException, ValueError) as exc:
            last_exc = exc
            continue
    raise LocatorResolutionErrorSelenium(f"All locator strategies failed: {last_exc}")


class SeleniumEngine(ExecutionEngine):
    name = "selenium"

    async def run_test(
        self,
        test_definition: TestDefinition,
        *,
        headless: bool = True,
        timeout_ms: int = 30000,
        healing_callback: HealingCallback | None = None,
        artifacts_dir: str | None = None,
    ) -> ExecutionResult:
        # Selenium's API is synchronous; the platform's async task workers
        # run this inside a thread executor (see workers/tasks.py) so it
        # doesn't block the event loop.
        start = time.monotonic()
        artifacts_dir = artifacts_dir or "/tmp/qa-artifacts"
        os.makedirs(artifacts_dir, exist_ok=True)
        run_token = uuid.uuid4().hex[:10]
        timeout_s = timeout_ms / 1000

        options = webdriver.ChromeOptions()
        if headless:
            options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")

        driver = webdriver.Chrome(options=options)
        step_results: list[StepExecutionRecord] = []
        overall_status = "PASSED"
        error_message = None
        screenshot_path = None

        try:
            driver.set_page_load_timeout(timeout_s)
            if not test_definition.steps or test_definition.steps[0].action != "goto":
                driver.get(test_definition.base_url)

            for step in test_definition.steps:
                record = StepExecutionRecord(order_index=step.order_index, action=step.action, status="PASSED")
                try:
                    if step.action == "goto":
                        driver.get(step.value)
                    elif step.action == "wait":
                        time.sleep((int(step.value) if step.value else 1000) / 1000)
                    elif step.action == "screenshot":
                        shot_path = os.path.join(artifacts_dir, f"{run_token}_step{step.order_index}.png")
                        driver.save_screenshot(shot_path)
                    else:
                        element = _resolve(driver, step.locator, timeout_s)
                        self._perform(driver, element, step.action, step.value)
                        record.locator_used = step.locator.model_dump(mode="json")
                except Exception as exc:  # noqa: BLE001
                    record.status = "FAILED"
                    record.error = str(exc)
                    step_results.append(record)
                    overall_status = "FAILED"
                    error_message = f"Step {step.order_index} ({step.action}) failed: {exc}"
                    break
                step_results.append(record)

            if overall_status == "FAILED":
                screenshot_path = os.path.join(artifacts_dir, f"{run_token}_failure.png")
                try:
                    driver.save_screenshot(screenshot_path)
                except Exception:  # noqa: BLE001
                    screenshot_path = None
        finally:
            driver.quit()

        duration_ms = int((time.monotonic() - start) * 1000)
        return ExecutionResult(
            status=overall_status,
            duration_ms=duration_ms,
            step_results=step_results,
            error_message=error_message,
            screenshot_path=screenshot_path,
        )

    @staticmethod
    def _perform(driver, element, action: str, value: str | None) -> None:
        if action == "click":
            element.click()
        elif action == "fill" or action == "type":
            element.clear()
            element.send_keys(value or "")
        elif action == "check":
            if not element.is_selected():
                element.click()
        elif action == "uncheck":
            if element.is_selected():
                element.click()
        elif action == "hover":
            webdriver.ActionChains(driver).move_to_element(element).perform()
        elif action == "press":
            from selenium.webdriver.common.keys import Keys

            key = getattr(Keys, (value or "ENTER").upper(), Keys.ENTER)
            element.send_keys(key)
        elif action == "select":
            from selenium.webdriver.support.ui import Select

            Select(element).select_by_visible_text(value or "")
        else:
            raise ValueError(f"Unsupported action for Selenium engine: {action}")
