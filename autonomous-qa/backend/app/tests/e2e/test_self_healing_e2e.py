"""End-to-end acceptance test for the platform's flagship scenario
(spec sections 34 and 57):

    discover (Login) -> execute login test -> PASS
    -> flip demo app's button to "Sign In"
    -> discover again -> change intelligence detects the rename
    -> re-execute the same test -> original locator fails
    -> self-healing discovers "Sign In" -> repairs -> retests -> PASS

This exercises the real discovery engine, the real deterministic
self-healing scorer, and the real Playwright execution engine end to
end. No step is hardcoded to "Login -> Sign In" — the healing engine
must independently rediscover the replacement from the live DOM, the
same way it would for any other relabeled control.

Requires: DEMO_APP_URL reachable with DEMO_MODE=true (so the test can
flip the label), and Playwright's chromium browser installed. Skipped
automatically otherwise.
"""
from __future__ import annotations

import os

import pytest

DEMO_APP_URL = os.environ.get("DEMO_APP_URL", "http://localhost:5050")


def _demo_app_in_test_mode() -> bool:
    import json
    import urllib.request

    try:
        req = urllib.request.Request(
            f"{DEMO_APP_URL}/debug/set-login-label",
            data=json.dumps({"label": "Login"}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=2) as resp:
            return resp.status == 200
    except Exception:  # noqa: BLE001
        return False


@pytest.mark.asyncio
@pytest.mark.skipif(
    not _demo_app_in_test_mode(),
    reason="demo-app is not running with DEMO_MODE=true",
)
async def test_self_healing_end_to_end_login_to_sign_in():
    import json
    import urllib.request

    from app.schemas.discovery import Locator
    from app.services.change_intelligence.change_detector import detect_change
    from app.services.change_intelligence.snapshot_comparator import compare_snapshots
    from app.services.discovery.crawler import discover_application
    from app.services.execution.engine import (
        AssertionDefinition,
        TestDefinition,
        TestStepDefinition,
    )
    from app.services.execution.playwright_engine import PlaywrightEngine
    from app.services.healing.healer import heal_step

    def set_label(label: str) -> None:
        req = urllib.request.Request(
            f"{DEMO_APP_URL}/debug/set-login-label",
            data=json.dumps({"label": label}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=2)

    def build_login_test(login_button_name: str) -> TestDefinition:
        return TestDefinition(
            test_case_id="e2e-login",
            name="User Login",
            base_url=f"{DEMO_APP_URL}/login",
            steps=[
                TestStepDefinition(
                    order_index=0,
                    action="fill",
                    target_element_id="email",
                    locator=Locator.model_validate(
                        {"primary": {"strategy": "id", "value": "email"}}
                    ),
                    value="demo@example.com",
                ),
                TestStepDefinition(
                    order_index=1,
                    action="fill",
                    target_element_id="password",
                    locator=Locator.model_validate(
                        {"primary": {"strategy": "id", "value": "password"}}
                    ),
                    value="password123",
                ),
                TestStepDefinition(
                    order_index=2,
                    action="click",
                    target_element_id="login_button",
                    # Deliberately role+name only, no test-id or id — this
                    # is exactly the kind of locator that breaks when a
                    # button's visible label changes, which is what makes
                    # this scenario a genuine self-healing test.
                    locator=Locator.model_validate(
                        {"primary": {"strategy": "role", "role": "button", "name": login_button_name}}
                    ),
                ),
            ],
            assertions=[
                AssertionDefinition(type="url", expected_value="/dashboard", locator=None),
            ],
        )

    engine = PlaywrightEngine()

    # --- Phase 1: version A ("Login"), test passes with its own locator ---
    set_label("Login")
    application_model_a = await discover_application(DEMO_APP_URL, max_pages=3)

    test_def_a = build_login_test("Login")
    result_a = await engine.run_test(test_def_a, headless=True, timeout_ms=15000)
    assert result_a.status == "PASSED", f"Baseline login test did not pass: {result_a.error_message}"

    # --- Phase 2: flip to version B ("Sign In") ---
    set_label("Sign In")
    application_model_b = await discover_application(DEMO_APP_URL, max_pages=3)

    diff = compare_snapshots(application_model_a, application_model_b)
    change = detect_change(diff)
    assert change.has_changes, "Change intelligence failed to detect the Login -> Sign In rename."
    assert any(
        "sign in" in (r.get("detail") or "").lower() for r in change.renamed
    ), "Rename was not attributed to the login control."

    # --- Phase 3: re-run the ORIGINAL (now-stale) test definition. Its
    # locator still says name="Login", which no longer exists, so the
    # engine must invoke self-healing to find "Sign In" and complete the
    # login — proving the repaired test actually passes end to end. ---
    async def healing_callback(page, step):
        return await heal_step(page, step)

    result_b = await engine.run_test(
        test_def_a,  # the STALE definition, unchanged, on purpose
        headless=True,
        timeout_ms=15000,
        healing_callback=healing_callback,
    )

    assert result_b.status == "HEALED", (
        f"Expected the stale test to be healed and pass, got status={result_b.status}, "
        f"error={result_b.error_message}"
    )
    assert result_b.healing_events, "No healing event was recorded despite a HEALED result."
    healed_event = result_b.healing_events[0]
    assert healed_event["outcome"] == "HEALED"
    assert healed_event["confidence"] >= 0.85

    # Reset for any subsequent test runs in the same session.
    set_label("Login")
