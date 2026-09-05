"""Extracts a JSON object from raw LLM text output.

Never trust raw LLM output: this is step one of the pipeline
(LLM response -> JSON extraction -> schema validation -> semantic
validation -> safety validation -> execution).
"""
from __future__ import annotations

import json
import re

from app.core.exceptions import InvalidTestPlanError

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


def extract_json_object(raw_text: str) -> dict:
    text = raw_text.strip()

    fence_match = _FENCE_RE.search(text)
    if fence_match:
        text = fence_match.group(1).strip()

    # If there's leading/trailing prose around the JSON, try to isolate
    # the outermost braces.
    if not text.startswith("{"):
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            text = text[start : end + 1]

    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise InvalidTestPlanError(f"AI response was not valid JSON: {exc}") from exc
