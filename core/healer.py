"""
core/healer.py
---------------
The self-healing core of AegisQA.

When a Playwright locator fails during test execution, Healer resolves the
*original intent* (role + accessible_name) against the live DOM/a11y snapshot
and returns a working replacement locator — in under HEALER_TIMEOUT_MS ms.

Public API:
    healer = Healer(run_id, step_index_getter)
    locator = healer.heal(failed_locator_intent, live_page)  -> Playwright Locator | None

HealEvent shape is documented in docs/SCHEMAS.md.
Every attempt (success or failure) is persisted to storage via storage/db.py.
"""

import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from typing import Any

from groq import Groq
from playwright.sync_api import Page

import storage.db as db
from config.settings import settings

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

_HEAL_SYSTEM = """You are an expert Playwright test automation engineer.
A locator broke because the web app was redesigned (different tag, id, or class).
Your job: find the element using ONLY ARIA accessibility attributes.

Given:
- original_intent: the role and accessible name the test was looking for
- a11y_snapshot: the live accessibility tree of the current page (JSON)

Respond with ONLY a JSON object (no prose, no markdown) with these fields:
{
  "found": true | false,
  "role": "<aria role>",
  "accessible_name": "<exact accessible name>",
  "strategy": "get_by_role" | "get_by_label" | "get_by_text",
  "value": "<the name/label/text to use>",
  "confidence": "high" | "medium" | "low",
  "reasoning": "<one sentence>"
}

Rules:
- Use get_by_role when the element has a clear ARIA role + accessible name.
- Use get_by_label for inputs with associated labels.
- Use get_by_text only as a last resort for visible text content.
- If you cannot find a reasonable match, set found=false."""

_HEAL_USER = """original_intent: {intent_json}

a11y_snapshot:
{snapshot_json}

Return the JSON healing strategy now."""


# ---------------------------------------------------------------------------
# Healer class
# ---------------------------------------------------------------------------

class Healer:
    """
    Self-healing locator resolver.

    Parameters
    ----------
    run_id : str
        The current test run ID (for DB persistence).
    """

    def __init__(self, run_id: str) -> None:
        self._run_id = run_id
        self._client = Groq(api_key=settings.GROQ_API_KEY)
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="healer")

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def heal(
        self,
        failed_locator_intent: dict,
        live_page: Page,
        step_index: int = 0,
    ) -> Any | None:
        """
        Attempt to resolve *failed_locator_intent* against the current DOM.

        Steps:
          1. Capture fresh a11y snapshot.
          2. Ask Groq (GROQ_MODEL_FAST) for a replacement strategy.
          3. Validate the candidate resolves to exactly 1 visible element.
          4. One retry with a broader query if first attempt yields 0 or >1.

        Returns a Playwright Locator on success, None on failure.
        Every attempt is recorded in storage/db.py.
        """
        t_start = time.monotonic()
        original_desc = self._intent_to_str(failed_locator_intent)

        # 1. Snapshot
        snapshot = self._snapshot(live_page)

        # 2. Groq call (hard timeout)
        strategy = self._call_groq_with_timeout(failed_locator_intent, snapshot)

        if strategy is None:
            latency = (time.monotonic() - t_start) * 1000
            log.warning("Healer: Groq call timed-out or failed (%.0f ms)", latency)
            self._persist(step_index, original_desc, None, latency, success=False)
            return None

        # 3. Validate (attempt 1)
        locator = self._build_locator(live_page, strategy)
        if locator is not None and self._is_unique_visible(locator):
            latency = (time.monotonic() - t_start) * 1000
            healed_desc = self._strategy_to_str(strategy)
            log.info(
                "Healer: healed '%s' → '%s' in %.0f ms",
                original_desc, healed_desc, latency,
            )
            self._persist(step_index, original_desc, healed_desc, latency, success=True)
            return locator

        # 4. One retry — broader: drop the name constraint, search by role only
        broader = dict(strategy)
        broader["strategy"] = "get_by_role"
        broader.pop("accessible_name", None)   # try without strict name match
        locator2 = self._build_locator(live_page, broader)
        latency = (time.monotonic() - t_start) * 1000

        if locator2 is not None and self._is_unique_visible(locator2):
            healed_desc = self._strategy_to_str(broader)
            log.info(
                "Healer: healed (retry) '%s' → '%s' in %.0f ms",
                original_desc, healed_desc, latency,
            )
            self._persist(step_index, original_desc, healed_desc, latency, success=True)
            return locator2

        log.warning(
            "Healer: could not resolve '%s' after retry (%.0f ms)", original_desc, latency
        )
        self._persist(step_index, original_desc, None, latency, success=False)
        return None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _snapshot(page: Page) -> str:
        """Return the page's ARIA snapshot as a string (Playwright >= 1.47)."""
        try:
            return page.aria_snapshot() or ""
        except Exception as exc:
            log.debug("aria_snapshot error: %s", exc)
            return ""

    def _call_groq_with_timeout(
        self, intent: dict, snapshot: str
    ) -> dict | None:
        """
        Submit a Groq request on a background thread and enforce
        HEALER_TIMEOUT_MS hard timeout.
        """
        timeout_s = settings.HEALER_TIMEOUT_MS / 1000.0

        future = self._executor.submit(self._call_groq, intent, snapshot)
        try:
            return future.result(timeout=timeout_s)
        except FuturesTimeout:
            future.cancel()
            log.warning(
                "Healer: Groq call exceeded %d ms -- aborting",
                settings.HEALER_TIMEOUT_MS,
            )
            return None
        except Exception as exc:
            log.error("Healer: Groq call raised: %s", exc)
            return None

    def _call_groq(self, intent: dict, snapshot: str) -> dict | None:
        """The actual (blocking) Groq inference call -- runs on the executor thread."""
        try:
            response = self._client.chat.completions.create(
                model=settings.GROQ_MODEL_FAST,
                messages=[
                    {"role": "system", "content": _HEAL_SYSTEM},
                    {
                        "role": "user",
                        "content": _HEAL_USER.format(
                            intent_json=json.dumps(intent, indent=2),
                            snapshot_json=snapshot[:4000],   # ARIA snapshot is already text
                        ),
                    },
                ],
                temperature=0.0,
                max_tokens=512,
                response_format={"type": "json_object"},
            )
            raw = response.choices[0].message.content or "{}"
            data = json.loads(raw)
            if not data.get("found", False):
                return None
            return data
        except Exception as exc:
            log.error("Healer Groq request failed: %s", exc)
            return None

    @staticmethod
    def _build_locator(page: Page, strategy: dict) -> Any | None:
        """Convert a healing strategy dict into a Playwright Locator."""
        strat = strategy.get("strategy", "get_by_role")
        role = strategy.get("role", "")
        name = strategy.get("accessible_name", strategy.get("value", ""))

        try:
            if strat == "get_by_role" and role:
                if name:
                    return page.get_by_role(role, name=name)  # type: ignore
                return page.get_by_role(role)  # type: ignore
            elif strat == "get_by_label":
                return page.get_by_label(name)
            elif strat == "get_by_text":
                return page.get_by_text(name)
            else:
                return page.get_by_role(role, name=name)  # type: ignore
        except Exception as exc:
            log.debug("_build_locator failed: %s", exc)
            return None

    @staticmethod
    def _is_unique_visible(locator) -> bool:
        """Return True if the locator resolves to exactly one visible element."""
        try:
            count = locator.count()
            if count != 1:
                log.debug("Healer: locator count=%d (expected 1)", count)
                return False
            locator.first.wait_for(state="visible", timeout=2_000)
            return True
        except Exception:
            return False

    @staticmethod
    def _intent_to_str(intent: dict) -> str:
        role = intent.get("role", "?")
        name = intent.get("accessible_name", intent.get("name", "?"))
        return f'role={role}[name="{name}"]'

    @staticmethod
    def _strategy_to_str(strategy: dict) -> str:
        strat = strategy.get("strategy", "?")
        val = strategy.get("accessible_name", strategy.get("value", "?"))
        role = strategy.get("role", "")
        if strat == "get_by_role":
            return f'role={role}[name="{val}"]'
        return f'{strat}("{val}")'

    def _persist(
        self,
        step_index: int,
        original: str | None,
        healed: str | None,
        latency_ms: float,
        success: bool,
    ) -> None:
        try:
            db.insert_heal_event(
                run_id=self._run_id,
                step_index=step_index,
                original_locator=original,
                healed_locator=healed,
                latency_ms=round(latency_ms, 1),
                success=success,
            )
        except Exception as exc:
            log.error("Healer: DB persist failed: %s", exc)

    def shutdown(self) -> None:
        """Cleanly shut down the background executor."""
        self._executor.shutdown(wait=False)
