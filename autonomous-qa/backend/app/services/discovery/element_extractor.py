"""Converts raw DOM extraction dicts into typed ElementModel instances
with a ranked, multi-strategy Locator attached to each element.

Locator priority (highest to lowest reliability):
1. data-testid
2. role + accessible name
3. label (for form fields)
4. name attribute
5. placeholder
6. stable HTML id
7. visible text
8. CSS (last-resort structural fallback)
"""
from __future__ import annotations

from app.schemas.discovery import ElementModel, Locator, LocatorStrategy


def _build_locator(raw: dict) -> Locator:
    fallbacks: list[LocatorStrategy] = []

    if raw.get("test_id"):
        primary = LocatorStrategy(strategy="testid", value=raw["test_id"])
    elif raw.get("role") and raw.get("text"):
        primary = LocatorStrategy(strategy="role", role=raw["role"], name=raw["text"])
    elif raw.get("aria_label"):
        primary = LocatorStrategy(strategy="label", value=raw["aria_label"])
    elif raw.get("name"):
        primary = LocatorStrategy(strategy="name", value=raw["name"])
    elif raw.get("placeholder"):
        primary = LocatorStrategy(strategy="placeholder", value=raw["placeholder"])
    elif raw.get("element_id_attr"):
        primary = LocatorStrategy(strategy="id", value=raw["element_id_attr"])
    elif raw.get("text"):
        primary = LocatorStrategy(strategy="text", value=raw["text"])
    else:
        primary = LocatorStrategy(
            strategy="css", value=f"{raw['tag']}:nth-of-type({raw.get('index', 0) + 1})"
        )

    candidate_order = [
        ("testid", raw.get("test_id")),
        ("role", raw.get("role") if raw.get("text") else None),
        ("label", raw.get("aria_label")),
        ("name", raw.get("name")),
        ("placeholder", raw.get("placeholder")),
        ("id", raw.get("element_id_attr")),
        ("text", raw.get("text")),
    ]
    for strategy, value in candidate_order:
        if not value:
            continue
        if strategy == primary.strategy:
            continue
        if strategy == "role":
            fb = LocatorStrategy(strategy="role", role=raw["role"], name=raw["text"])
        else:
            fb = LocatorStrategy(strategy=strategy, value=value)
        fallbacks.append(fb)

    # Always keep a CSS fallback as the last resort.
    fallbacks.append(
        LocatorStrategy(strategy="css", value=f"{raw['tag']}:nth-of-type({raw.get('index', 0) + 1})")
    )

    return Locator(primary=primary, fallbacks=fallbacks)


def to_element_model(raw: dict, page_url: str, element_id: str) -> ElementModel:
    return ElementModel(
        id=element_id,
        tag=raw["tag"],
        role=raw.get("role"),
        text=raw.get("text"),
        aria_label=raw.get("aria_label"),
        test_id=raw.get("test_id"),
        name=raw.get("name"),
        placeholder=raw.get("placeholder"),
        element_id_attr=raw.get("element_id_attr"),
        href=raw.get("href"),
        input_type=raw.get("input_type"),
        visible=raw.get("visible", True),
        enabled=raw.get("enabled", True),
        page_url=page_url,
        locators=_build_locator(raw),
    )
