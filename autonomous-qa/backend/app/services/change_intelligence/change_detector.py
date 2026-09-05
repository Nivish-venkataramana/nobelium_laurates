"""Turns a raw SnapshotDiff into a structured, explainable UI_CHANGE
summary that the API/frontend/risk-engine can consume."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

from app.services.change_intelligence.snapshot_comparator import ElementChange, SnapshotDiff


@dataclass
class UIChange:
    has_changes: bool
    total_changes: int
    added: list[dict] = field(default_factory=list)
    removed: list[dict] = field(default_factory=list)
    renamed: list[dict] = field(default_factory=list)
    attribute_changed: list[dict] = field(default_factory=list)
    added_pages: list[str] = field(default_factory=list)
    removed_pages: list[str] = field(default_factory=list)
    summary: str = ""


def _serialize(changes: list[ElementChange]) -> list[dict]:
    return [asdict(c) for c in changes]


def detect_change(diff: SnapshotDiff) -> UIChange:
    parts = []
    if diff.renamed_elements:
        parts.append(f"{len(diff.renamed_elements)} element(s) renamed")
    if diff.added_elements:
        parts.append(f"{len(diff.added_elements)} element(s) added")
    if diff.removed_elements:
        parts.append(f"{len(diff.removed_elements)} element(s) removed")
    if diff.attribute_changes:
        parts.append(f"{len(diff.attribute_changes)} element(s) changed attributes")
    if diff.added_pages:
        parts.append(f"{len(diff.added_pages)} new page(s)")
    if diff.removed_pages:
        parts.append(f"{len(diff.removed_pages)} page(s) removed")

    summary = "No UI changes detected." if not parts else "Detected: " + ", ".join(parts) + "."

    return UIChange(
        has_changes=diff.has_changes,
        total_changes=diff.total_change_count,
        added=_serialize(diff.added_elements),
        removed=_serialize(diff.removed_elements),
        renamed=_serialize(diff.renamed_elements),
        attribute_changed=_serialize(diff.attribute_changes),
        added_pages=diff.added_pages,
        removed_pages=diff.removed_pages,
        summary=summary,
    )
