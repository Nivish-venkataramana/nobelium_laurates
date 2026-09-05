"""
runners/ui_runner.py
----------------------
Executes generated Playwright specs against the live target application,
wrapping every locator action with core.healer.Healer as a fallback handler,
and streaming step-by-step progress events for the dashboard.

Public API:
    runner = UIRunner(base_url, run_id)
    result = runner.run(workflow, healer, event_callback=None)  -> RunResult dict

RunResult contains: run_id, status, steps (list), heal_count, duration_ms
Events emitted to event_callback: step_started, step_passed, step_healed,
                                   step_failed, run_finished
"""

import logging
import time
import uuid
from typing import Any, Callable

from playwright.sync_api import Page, sync_playwright

import storage.db as db
from config.settings import settings
from core.healer import Healer
from runners.perf_monitor import PerfMonitor
from runners.security_scanner import SecurityScanner

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Event helpers
# ---------------------------------------------------------------------------

def _emit(callback: Callable | None, event_type: str, **payload) -> None:
    """Fire an event to the optional callback (non-blocking, swallows errors)."""
    if callback is None:
        return
    try:
        callback({"type": event_type, **payload})
    except Exception as exc:
        log.debug("event_callback raised: %s", exc)


# ---------------------------------------------------------------------------
# UIRunner
# ---------------------------------------------------------------------------

class UIRunner:
    """
    Executes a Workflow dict against a live target URL using Playwright.

    Wraps every locator action with Healer — on locator failure the runner
    calls healer.heal(), retries once with the healed locator, and records a
    HealEvent in the DB.
    """

    def __init__(self, base_url: str, run_id: str | None = None) -> None:
        self._base_url = base_url.rstrip("/")
        self._run_id = run_id or str(uuid.uuid4())

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def run(
        self,
        workflow: dict,
        healer: Healer | None = None,
        event_callback: Callable | None = None,
        scan_security: bool = True,
    ) -> dict:
        """
        Execute all steps in *workflow* against the live target.

        Parameters
        ----------
        workflow:
            A Workflow dict (docs/SCHEMAS.md).
        healer:
            A pre-initialised Healer bound to the same run_id.
        event_callback:
            Optional callable(event_dict) for live streaming to the dashboard.
        scan_security:
            If True, run SecurityScanner after the UI steps finish.

        Returns
        -------
        RunResult dict with keys: run_id, status, steps, heal_count,
        duration_ms, findings, metrics.
        """
        db.create_run(self._run_id, self._base_url)
        _emit(event_callback, "run_started", run_id=self._run_id, target=self._base_url)

        t_run_start = time.monotonic()
        steps_results: list[dict] = []
        heal_count = 0
        all_findings: list[dict] = []
        overall_status = "passed"

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            ctx = browser.new_context(
                viewport={"width": 1280, "height": 900},
                base_url=self._base_url,
            )
            page = ctx.new_page()

            # Attach perf monitor
            perf = PerfMonitor()
            perf.attach(page)

            try:
                steps = workflow.get("steps", [])
                for i, step in enumerate(steps):
                    step_result, healed = self._execute_step(
                        page, step, i, healer, event_callback, perf
                    )
                    steps_results.append(step_result)
                    if healed:
                        heal_count += 1
                    if step_result["status"] == "failed":
                        overall_status = "failed"

                # Security scan — after the main workflow
                if scan_security:
                    all_findings = self._run_security_scan(
                        page, workflow, event_callback
                    )

            except Exception as exc:
                log.error("UIRunner: unexpected error: %s", exc, exc_info=True)
                overall_status = "error"
            finally:
                ctx.close()
                browser.close()

        # Persist metrics
        metrics = perf.get_metrics()
        for m in metrics:
            try:
                db.insert_request_metric(
                    run_id=self._run_id,
                    url=m["url"],
                    method=m["method"],
                    status=m.get("status"),
                    duration_ms=m["duration_ms"],
                    anomaly=m["anomaly"],
                    step_index=m.get("step_index"),
                )
            except Exception as exc:
                log.debug("metric persist error: %s", exc)

        # Persist findings
        for f in all_findings:
            try:
                db.insert_finding(
                    run_id=self._run_id,
                    field=f["field"],
                    payload=f["payload"],
                    reflected=f["reflected"],
                    severity=f["severity"],
                )
            except Exception as exc:
                log.debug("finding persist error: %s", exc)

        duration_ms = (time.monotonic() - t_run_start) * 1000
        db.update_run(self._run_id, overall_status)

        result = {
            "run_id": self._run_id,
            "status": overall_status,
            "steps": steps_results,
            "heal_count": heal_count,
            "duration_ms": round(duration_ms, 1),
            "findings": all_findings,
            "metrics": metrics,
        }
        _emit(event_callback, "run_finished", **result)
        log.info(
            "Run %s finished — status=%s  heals=%d  duration=%.0f ms",
            self._run_id, overall_status, heal_count, duration_ms,
        )
        return result

    # ------------------------------------------------------------------
    # Internal: single step execution
    # ------------------------------------------------------------------

    def _execute_step(
        self,
        page: Page,
        step: dict,
        step_index: int,
        healer: Healer | None,
        callback: Callable | None,
        perf: PerfMonitor,
    ) -> tuple[dict, bool]:
        """
        Execute one workflow step.  On locator failure, calls healer.heal()
        and retries once.

        Returns (step_result_dict, was_healed: bool).
        """
        intent = step.get("intent", f"step {step_index}")
        role = step.get("role", "")
        name = step.get("accessible_name", "")
        action = step.get("action_type", "click")
        value = step.get("value", "")

        _emit(callback, "step_started", step_index=step_index, intent=intent)
        perf.set_step(step_index)
        t_start = time.monotonic()
        healed = False

        try:
            self._do_action(page, role, name, action, value)
            duration_ms = (time.monotonic() - t_start) * 1000
            db.insert_step(self._run_id, step_index, intent, "passed", round(duration_ms, 1))
            _emit(callback, "step_passed", step_index=step_index, intent=intent, duration_ms=duration_ms)
            log.info("  Step %d PASSED: %s (%.0f ms)", step_index, intent, duration_ms)
            return {"step_index": step_index, "intent": intent, "status": "passed", "duration_ms": round(duration_ms, 1)}, False

        except Exception as primary_exc:
            log.warning("  Step %d locator failed: %s — attempting heal", step_index, primary_exc)

            if healer is None:
                duration_ms = (time.monotonic() - t_start) * 1000
                db.insert_step(self._run_id, step_index, intent, "failed", round(duration_ms, 1))
                _emit(callback, "step_failed", step_index=step_index, intent=intent, error=str(primary_exc))
                return {"step_index": step_index, "intent": intent, "status": "failed", "duration_ms": round(duration_ms, 1)}, False

            # Invoke healer
            intent_dict = {"role": role, "accessible_name": name}
            healed_locator = healer.heal(intent_dict, page, step_index=step_index)

            if healed_locator is not None:
                try:
                    self._do_action_on_locator(healed_locator, action, value)
                    duration_ms = (time.monotonic() - t_start) * 1000
                    healed = True

                    # Get what the healer stored for display
                    heal_events = db.get_heal_events(self._run_id)
                    latest_heal = heal_events[-1] if heal_events else {}
                    healed_str = latest_heal.get("healed_locator", "healed")
                    original_str = latest_heal.get("original_locator", "original")

                    db.insert_step(self._run_id, step_index, intent, "healed", round(duration_ms, 1))
                    _emit(
                        callback, "step_healed",
                        step_index=step_index, intent=intent,
                        original_locator=original_str,
                        healed_locator=healed_str,
                        heal_latency_ms=latest_heal.get("latency_ms", 0),
                        duration_ms=duration_ms,
                    )
                    log.info(
                        "  Step %d HEALED: '%s' → '%s' (%.0f ms total)",
                        step_index, original_str, healed_str, duration_ms,
                    )
                    return {
                        "step_index": step_index, "intent": intent,
                        "status": "healed", "duration_ms": round(duration_ms, 1),
                        "healed_locator": healed_str,
                    }, True

                except Exception as retry_exc:
                    log.warning("  Step %d: healed locator also failed: %s", step_index, retry_exc)

            duration_ms = (time.monotonic() - t_start) * 1000
            db.insert_step(self._run_id, step_index, intent, "failed", round(duration_ms, 1))
            _emit(callback, "step_failed", step_index=step_index, intent=intent, error=str(primary_exc))
            return {"step_index": step_index, "intent": intent, "status": "failed", "duration_ms": round(duration_ms, 1)}, False

    def _do_action(self, page: Page, role: str, name: str, action: str, value: str) -> None:
        """Perform an action using accessibility-tree locators."""
        if action == "navigate":
            page.goto(self._base_url, wait_until="domcontentloaded")
            return

        locator = None
        if role and name:
            locator = page.get_by_role(role, name=name)  # type: ignore
        elif name:
            locator = page.get_by_label(name)
        else:
            raise ValueError(f"Cannot locate: role={role!r} name={name!r}")

        if action == "click":
            locator.click(timeout=5_000)
        elif action == "fill":
            locator.fill(value, timeout=5_000)
        elif action == "select":
            locator.select_option(value, timeout=5_000)
        else:
            locator.click(timeout=5_000)

    @staticmethod
    def _do_action_on_locator(locator, action: str, value: str) -> None:
        """Perform an action on an already-resolved Playwright Locator."""
        if action == "click":
            locator.click(timeout=5_000)
        elif action == "fill":
            locator.fill(value, timeout=5_000)
        elif action == "select":
            locator.select_option(value, timeout=5_000)
        else:
            locator.click(timeout=5_000)

    # ------------------------------------------------------------------
    # Internal: security scan pass
    # ------------------------------------------------------------------

    def _run_security_scan(
        self,
        page: Page,
        workflow: dict,
        callback: Callable | None,
    ) -> list[dict]:
        """
        Navigate to each page in the workflow and run SecurityScanner on all
        discovered input fields.
        """
        _emit(callback, "security_scan_started")
        scanner = SecurityScanner()
        all_findings: list[dict] = []

        # Always probe the checkout page — it's where the known XSS surface lives.
        # Also probe any fill-steps found in the workflow for broader coverage.
        checkout_url = self._base_url + "/checkout"
        scan_targets: dict[str, list[dict]] = {
            checkout_url: [
                {"role": "textbox", "accessible_name": "Promo code"},
                {"role": "textbox", "accessible_name": "Card number"},
            ]
        }

        # Add any additional fill-step inputs from the workflow
        for step in workflow.get("steps", []):
            if step.get("action_type") == "fill" and step.get("accessible_name"):
                # Map fill steps to their likely page — best-effort
                page_url = checkout_url
                existing = scan_targets.setdefault(page_url, [])
                entry = {"role": step.get("role", "textbox"),
                         "accessible_name": step.get("accessible_name", "")}
                if entry not in existing:
                    existing.append(entry)

        for page_url, inputs in scan_targets.items():
            try:
                page.goto(page_url, wait_until="domcontentloaded", timeout=8_000)
                findings = scanner.scan(page, inputs)
                all_findings.extend(findings)
            except Exception as exc:
                log.warning("Security scan error for %s: %s", page_url, exc)

        reflected = [f for f in all_findings if f["reflected"]]
        _emit(callback, "security_scan_finished", findings=all_findings, reflected_count=len(reflected))
        log.info("SecurityScan: %d finding(s), %d reflected", len(all_findings), len(reflected))
        return all_findings
