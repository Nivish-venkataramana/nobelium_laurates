"""Deterministic interpreter for the allowlisted action set.

The AI never executes anything. This module is the only place that
turns a validated Action + Locator into a real Playwright call. It
knows nothing about AI; it just interprets already-validated data.
"""
from __future__ import annotations

from typing import Any

from app.core.exceptions import ExecutionError
from app.schemas.discovery import Locator, LocatorStrategy


class LocatorResolutionError(ExecutionError):
    safe_message = "No locator strategy could find the target element."


async def resolve_locator(page: Any, locator: Locator, timeout_ms: int = 5000) -> Any:
    """Try the primary strategy, then each fallback in order. Returns the
    first Playwright Locator that resolves to at least one visible
    element. Raises LocatorResolutionError if none succeed.
    """
    strategies = [locator.primary, *locator.fallbacks]
    last_error: Exception | None = None

    for strat in strategies:
        try:
            pw_locator = _strategy_to_playwright_locator(page, strat)
            await pw_locator.first.wait_for(state="attached", timeout=timeout_ms)
            return pw_locator.first
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            continue

    raise LocatorResolutionError(
        f"All {len(strategies)} locator strategies failed. Last error: {last_error}"
    )


def _strategy_to_playwright_locator(page: Any, strat: LocatorStrategy) -> Any:
    if strat.strategy == "testid":
        return page.get_by_test_id(strat.value)
    if strat.strategy == "role":
        return page.get_by_role(strat.role or "button", name=strat.name)
    if strat.strategy == "label":
        return page.get_by_label(strat.value)
    if strat.strategy == "name":
        return page.locator(f'[name="{strat.value}"]')
    if strat.strategy == "placeholder":
        return page.get_by_placeholder(strat.value)
    if strat.strategy == "id":
        return page.locator(f"#{strat.value}")
    if strat.strategy == "text":
        return page.get_by_text(strat.value, exact=False)
    if strat.strategy == "css":
        return page.locator(strat.value)
    if strat.strategy == "xpath":
        return page.locator(f"xpath={strat.value}")
    raise ValueError(f"Unknown locator strategy: {strat.strategy}")


async def perform_action(page: Any, action: str, element: Any | None, value: str | None) -> None:
    """Execute a single allowlisted action. `element` is a resolved
    Playwright Locator (or None for goto/wait/screenshot)."""
    if action == "goto":
        await page.goto(value)
    elif action == "click":
        await element.click()
    elif action == "fill":
        await element.fill(value or "")
    elif action == "type":
        await element.type(value or "")
    elif action == "select":
        await element.select_option(value)
    elif action == "check":
        await element.check()
    elif action == "uncheck":
        await element.uncheck()
    elif action == "hover":
        await element.hover()
    elif action == "press":
        await element.press(value or "Enter")
    elif action == "wait":
        await page.wait_for_timeout(int(value) if value else 1000)
    elif action == "screenshot":
        pass  # handled by the caller, which has access to result storage
    else:
        raise ExecutionError(f"Action '{action}' is not supported by the interpreter.")
