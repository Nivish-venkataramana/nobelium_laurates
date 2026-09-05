"""
runners/security_scanner.py
------------------------------
Passive, non-destructive security prober for input fields discovered by
core/crawler.py.

Submits standard OWASP boundary/XSS payloads into each text-like input ONE
AT A TIME, then inspects the response DOM for unescaped reflection — without
crashing or corrupting the target app's state.

Public API:
    scanner = SecurityScanner()
    findings = scanner.scan(page, discovered_inputs)  -> list[Finding]

Finding shape is documented in docs/SCHEMAS.md.
"""

import logging
import re
import time
from urllib.parse import urlencode, urljoin, urlparse

from playwright.sync_api import Page

from config.settings import settings

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Payload definitions
# ---------------------------------------------------------------------------

_STANDARD_PAYLOADS: list[str] = [
    # XSS reflection probes (harmless — only console.log, no network calls)
    '"><script>console.log(1)</script>',
    "'><img src=x onerror=console.log(2)>",
    "<svg onload=console.log(3)>",
    # Long-string overflow (boundary check)
    "A" * 512,
    # SQLi-looking strings (no destructive keywords)
    "' OR '1'='1",
    "1; SELECT 1--",
]

_EXTENDED_PAYLOADS: list[str] = _STANDARD_PAYLOADS + [
    '"><details open ontoggle=console.log(4)>',
    "javascript:console.log(5)",
    "<" + "s" * 200 + ">",
    "\x00\x0a\x0d",
    "{{7*7}}",          # SSTI probe
]


def _payloads() -> list[str]:
    if settings.OWASP_PAYLOAD_SET == "extended":
        return _EXTENDED_PAYLOADS
    return _STANDARD_PAYLOADS


# ---------------------------------------------------------------------------
# SecurityScanner class
# ---------------------------------------------------------------------------

class SecurityScanner:
    """
    Non-destructive XSS/reflection security scanner.

    Sends OWASP boundary probes into every discovered text input, then checks
    the raw response HTML for unescaped reflection.
    """

    def scan(self, page: Page, discovered_inputs: list[dict]) -> list[dict]:
        """
        Probe each input in *discovered_inputs* with all configured payloads.

        Parameters
        ----------
        page:
            A live Playwright Page — should be on the page that contains the
            inputs. The scanner will navigate back after each probe.
        discovered_inputs:
            List of dicts with at least {"accessible_name": ..., "role": ...}.
            Typically the "fields" list from a CrawlGraph form.

        Returns
        -------
        List of Finding dicts (docs/SCHEMAS.md).
        """
        findings: list[dict] = []
        payloads = _payloads()
        base_url = page.url

        text_inputs = [
            inp for inp in discovered_inputs
            if inp.get("role") in ("textbox", "searchbox")
            or inp.get("input_type") in ("text", "search", "email", "url", None)
        ]

        log.info(
            "SecurityScanner: probing %d input(s) with %d payload(s)",
            len(text_inputs), len(payloads),
        )

        for inp in text_inputs:
            field_name = inp.get("accessible_name") or inp.get("name") or "unknown"

            for payload in payloads:
                finding = self._probe(page, base_url, inp, field_name, payload)
                if finding is not None:
                    findings.append(finding)
                    # Navigate back to base for the next probe
                    try:
                        page.goto(base_url, wait_until="domcontentloaded", timeout=8_000)
                    except Exception:
                        pass

        log.info(
            "SecurityScanner: %d finding(s) — %d reflected",
            len(findings),
            sum(1 for f in findings if f["reflected"]),
        )
        return findings

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _probe(
        self,
        page: Page,
        base_url: str,
        inp: dict,
        field_name: str,
        payload: str,
    ) -> dict | None:
        """
        Submit *payload* into the field described by *inp* and check for
        unescaped reflection.

        Returns a Finding dict (reflected or not) or None on error.
        """
        try:
            # Try to locate the field by accessible name, then by label
            locator = self._find_field(page, inp)
            if locator is None:
                log.debug("Scanner: cannot locate field '%s' — skipping", field_name)
                return None

            locator.fill(payload)
            locator.press("Enter")

            # Small wait for page to load after submission
            page.wait_for_load_state("domcontentloaded", timeout=5_000)

            html = page.content()
            reflected, evidence = self._check_reflection(payload, html)

            severity = "medium" if reflected and "<script" in payload.lower() else "low"

            return {
                "field": field_name,
                "payload": payload,
                "reflected": reflected,
                "severity": severity if reflected else "info",
                "evidence": evidence,
            }

        except Exception as exc:
            log.debug("Scanner probe error (%s / %r): %s", field_name, payload[:30], exc)
            return None

    @staticmethod
    def _find_field(page: Page, inp: dict):
        """Locate an input using accessible name or label."""
        name = inp.get("accessible_name", "")
        role = inp.get("role", "textbox")
        try:
            loc = page.get_by_role(role, name=name).first  # type: ignore
            loc.wait_for(state="visible", timeout=3_000)
            return loc
        except Exception:
            pass
        try:
            loc = page.get_by_label(name).first
            loc.wait_for(state="visible", timeout=2_000)
            return loc
        except Exception:
            return None

    @staticmethod
    def _check_reflection(payload: str, html: str) -> tuple[bool, str]:
        """
        Check if *payload* appears unescaped in *html*.

        Returns (reflected: bool, evidence: str).
        """
        # Check for verbatim (unescaped) presence — ignore HTML-encoded versions
        if payload in html:
            # Find a short excerpt for evidence
            idx = html.index(payload)
            start = max(0, idx - 40)
            end = min(len(html), idx + len(payload) + 40)
            excerpt = html[start:end].replace("\n", " ")
            return True, f"payload found unescaped in response HTML: ...{excerpt}..."

        # Also check for partial XSS-critical substrings (e.g. <script> sans quote wrapper)
        critical = ["<script", "<img", "<svg", "onerror=", "onload="]
        for crit in critical:
            if crit.lower() in html.lower() and crit.lower() in payload.lower():
                return True, f"critical substring '{crit}' reflected unescaped"

        return False, "no unescaped reflection detected"
