"""
core/intent_engine.py
----------------------
Turns raw crawler telemetry (accessibility tree + interactive elements) into
high-level, human-readable user workflows using Groq inference, then compiles
those workflows into executable Playwright test specs.

Public API:
    engine = IntentEngine()
    workflows = engine.synthesize_workflows(crawl_graph)   -> list[Workflow]
    spec_path = engine.generate_playwright_spec(workflow)  -> str (file path)

Workflow shape is documented in docs/SCHEMAS.md.
Generated specs use get_by_role / get_by_label / get_by_text — never CSS/XPath.
"""

import json
import logging
import re
import textwrap
from pathlib import Path
from typing import Any

from groq import Groq

from config.settings import settings

log = logging.getLogger(__name__)

_SPECS_DIR = Path("tests/generated_specs")


# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

_SYNTHESIS_SYSTEM = """You are an expert QA engineer. Given a JSON crawl graph of a web application,
produce a list of user workflows (end-to-end test scenarios) that cover the main user journeys.

For each workflow, output a JSON object with:
  "name"  : short descriptive name (snake_case)
  "steps" : ordered list of steps, each step having:
      "intent"           : what the user is trying to do (plain English)
      "role"             : ARIA role of the element (e.g. "button", "textbox", "link")
      "accessible_name"  : the element's accessible name / label
      "action_type"      : one of "click", "fill", "select", "navigate"
      "value"            : for "fill"/"select" only — the value to enter (use "" otherwise)
      "expected_outcome" : what should be visible/true after this step

Return ONLY a JSON array of workflow objects, no markdown fences, no prose.
Focus on the login-to-checkout happy path and at least one negative path."""

_SYNTHESIS_USER = """Crawl graph:
{graph_json}

Produce the JSON workflow array now."""


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class IntentEngine:
    """
    Synthesises Groq-generated test workflows from a CrawlGraph and emits
    Playwright specs that use only accessibility-tree locators.
    """

    def __init__(self) -> None:
        self._client = Groq(api_key=settings.GROQ_API_KEY)

    # ------------------------------------------------------------------
    # Workflow synthesis
    # ------------------------------------------------------------------

    def synthesize_workflows(self, crawl_graph: dict) -> list[dict]:
        """
        Send the crawl graph to Groq (GROQ_MODEL_REASONING) and parse the
        returned workflow list.

        Returns a list of Workflow dicts matching docs/SCHEMAS.md.
        """
        graph_json = json.dumps(crawl_graph, indent=2)

        log.info("Synthesising workflows via Groq (%s)…", settings.GROQ_MODEL_REASONING)
        response = self._client.chat.completions.create(
            model=settings.GROQ_MODEL_REASONING,
            messages=[
                {"role": "system", "content": _SYNTHESIS_SYSTEM},
                {"role": "user", "content": _SYNTHESIS_USER.format(graph_json=graph_json)},
            ],
            temperature=0.2,
            max_tokens=4096,
            response_format={"type": "json_object"},
        )

        raw = response.choices[0].message.content or "{}"
        workflows = self._parse_workflows(raw)
        log.info("Synthesised %d workflow(s)", len(workflows))
        return workflows

    def _parse_workflows(self, raw: str) -> list[dict]:
        """
        Parse the Groq response — handles both a bare array and a
        {"workflows": [...]} envelope that some models return.
        """
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            log.error("Failed to parse Groq JSON response: %s\nRaw: %s", exc, raw[:500])
            return [self._fallback_workflow()]

        if isinstance(data, list):
            return data
        # Unwrap common envelope keys
        for key in ("workflows", "items", "results"):
            if isinstance(data.get(key), list):
                return data[key]
        # If it's a single workflow object, wrap it
        if "steps" in data:
            return [data]
        log.warning("Unexpected Groq response shape — using fallback workflow")
        return [self._fallback_workflow()]

    @staticmethod
    def _fallback_workflow() -> dict:
        """Hard-coded login→cart→checkout workflow used when Groq fails."""
        return {
            "name": "login_cart_checkout",
            "steps": [
                {
                    "intent": "navigate to the application home page",
                    "role": "link",
                    "accessible_name": "Home",
                    "action_type": "navigate",
                    "value": "",
                    "expected_outcome": "login form is visible",
                },
                {
                    "intent": "enter username",
                    "role": "textbox",
                    "accessible_name": "Username",
                    "action_type": "fill",
                    "value": "demo_user",
                    "expected_outcome": "username field contains the value",
                },
                {
                    "intent": "enter password",
                    "role": "textbox",
                    "accessible_name": "Password",
                    "action_type": "fill",
                    "value": "password123",
                    "expected_outcome": "password field is filled",
                },
                {
                    "intent": "click Sign In to authenticate",
                    "role": "button",
                    "accessible_name": "Sign In",
                    "action_type": "click",
                    "value": "",
                    "expected_outcome": "cart page is shown",
                },
                {
                    "intent": "proceed to checkout from cart",
                    "role": "link",
                    "accessible_name": "Proceed to checkout",
                    "action_type": "click",
                    "value": "",
                    "expected_outcome": "checkout page is visible",
                },
                {
                    "intent": "submit checkout form",
                    "role": "button",
                    "accessible_name": "Checkout",
                    "action_type": "click",
                    "value": "",
                    "expected_outcome": "order confirmation page is shown",
                },
            ],
        }

    # ------------------------------------------------------------------
    # Playwright spec generation
    # ------------------------------------------------------------------

    def generate_playwright_spec(self, workflow: dict) -> str:
        """
        Compile a Workflow dict into a standalone Python Playwright script,
        writing it to tests/generated_specs/<name>.py.

        Uses ONLY accessibility-tree locators:
            page.get_by_role(...)
            page.get_by_label(...)
            page.get_by_text(...)

        Returns the path to the written spec file.
        """
        _SPECS_DIR.mkdir(parents=True, exist_ok=True)
        name = re.sub(r"[^\w]", "_", workflow.get("name", "workflow").lower())
        spec_path = _SPECS_DIR / f"{name}.py"

        steps_code = self._compile_steps(workflow.get("steps", []))

        spec = textwrap.dedent(f'''\
            """
            AegisQA generated spec: {workflow.get("name")}
            AUTO-GENERATED — do not edit by hand.
            Uses only accessibility-tree locators so core.healer can recover them.
            """

            import pytest
            from playwright.sync_api import Page, expect


            BASE_URL = "http://localhost:5000"


            def test_{name}(page: Page) -> None:
                """End-to-end: {workflow.get("name")}"""
                page.goto(BASE_URL)

            {steps_code}
        ''')

        spec_path.write_text(spec, encoding="utf-8")
        log.info("Spec written → %s", spec_path)
        return str(spec_path)

    @staticmethod
    def _compile_steps(steps: list[dict]) -> str:
        """Turn a list of Workflow steps into indented Playwright Python lines."""
        lines: list[str] = []
        for i, step in enumerate(steps):
            role = step.get("role", "")
            name = step.get("accessible_name", "")
            action = step.get("action_type", "click")
            value = step.get("value", "")
            intent = step.get("intent", "")

            lines.append(f"    # Step {i + 1}: {intent}")

            if action == "navigate":
                lines.append(f"    page.goto(BASE_URL)")

            elif action == "fill":
                if name:
                    lines.append(
                        f"    page.get_by_role({role!r}, name={name!r}).fill({value!r})"
                    )
                    # Also try get_by_label as fallback hint in comments
                    lines.append(
                        f"    # alt: page.get_by_label({name!r}).fill({value!r})"
                    )
                else:
                    lines.append(f"    # WARNING: no accessible_name for fill step {i+1}")

            elif action == "click":
                if role and name:
                    lines.append(
                        f"    page.get_by_role({role!r}, name={name!r}).click()"
                    )
                elif name:
                    lines.append(
                        f"    page.get_by_text({name!r}).click()"
                    )
                else:
                    lines.append(f"    # WARNING: no role/name for click step {i+1}")

            elif action == "select":
                if name:
                    lines.append(
                        f"    page.get_by_role({role!r}, name={name!r}).select_option({value!r})"
                    )

            lines.append("")   # blank line between steps

        return "\n".join(lines)
