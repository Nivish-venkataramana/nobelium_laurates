"""Finds candidate replacement elements in the CURRENT live DOM for a
step whose original locator failed to resolve.

This re-uses the same discovery extraction used by the crawler, so
candidates are drawn from real, present elements — never invented.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from app.schemas.discovery import ElementModel
from app.services.discovery.dom_analyzer import extract_page_elements
from app.services.discovery.element_extractor import to_element_model


@dataclass
class HealingCandidate:
    element: ElementModel


async def find_candidates(page: Any, tag_filter: str | None = None) -> list[HealingCandidate]:
    """Extract all currently-interactive elements on the page as healing
    candidates. Optionally filter by tag (e.g. only 'button' elements)
    to keep the candidate set relevant to the failed step's element type.
    """
    raw_elements = await extract_page_elements(page)
    page_url = page.url
    candidates: list[HealingCandidate] = []
    for raw in raw_elements:
        if raw.get("is_form"):
            continue
        if not raw.get("visible", True):
            continue
        if tag_filter and raw.get("tag") != tag_filter:
            continue
        element = to_element_model(raw, page_url, f"cand_{uuid.uuid4().hex[:8]}")
        candidates.append(HealingCandidate(element=element))
    return candidates
