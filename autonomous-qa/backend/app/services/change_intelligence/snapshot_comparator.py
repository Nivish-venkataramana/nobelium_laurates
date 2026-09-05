"""Diffs two ApplicationSnapshots' semantic models to find added,
removed, renamed, moved, and attribute-changed elements — purely
deterministic set/field comparison, no AI involved.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from rapidfuzz import fuzz

from app.schemas.discovery import ApplicationModel, ElementModel

_RENAME_SIMILARITY_THRESHOLD = 45  # rapidfuzz 0-100 scale


def _element_fingerprint(e: ElementModel) -> str:
    """A structural fingerprint used to match "the same" element across
    snapshots even when its label text changed. Deliberately excludes
    text/aria_label so renames can be detected as renames, not
    add+remove pairs."""
    return "|".join(
        [
            e.tag,
            e.role or "",
            e.test_id or "",
            e.name or "",
            e.element_id_attr or "",
            e.page_url,
        ]
    )


@dataclass
class ElementChange:
    change_type: str  # ADDED | REMOVED | RENAMED | ATTRIBUTE_CHANGED | MOVED
    element_id_before: str | None
    element_id_after: str | None
    before: dict | None
    after: dict | None
    detail: str


@dataclass
class SnapshotDiff:
    added_elements: list[ElementChange] = field(default_factory=list)
    removed_elements: list[ElementChange] = field(default_factory=list)
    renamed_elements: list[ElementChange] = field(default_factory=list)
    attribute_changes: list[ElementChange] = field(default_factory=list)
    added_pages: list[str] = field(default_factory=list)
    removed_pages: list[str] = field(default_factory=list)
    added_forms: int = 0
    removed_forms: int = 0
    added_navigation: int = 0
    removed_navigation: int = 0

    @property
    def has_changes(self) -> bool:
        return bool(
            self.added_elements
            or self.removed_elements
            or self.renamed_elements
            or self.attribute_changes
            or self.added_pages
            or self.removed_pages
        )

    @property
    def total_change_count(self) -> int:
        return (
            len(self.added_elements)
            + len(self.removed_elements)
            + len(self.renamed_elements)
            + len(self.attribute_changes)
        )


def compare_snapshots(previous: ApplicationModel, current: ApplicationModel) -> SnapshotDiff:
    diff = SnapshotDiff()

    prev_urls = {p.url for p in previous.pages}
    curr_urls = {p.url for p in current.pages}
    diff.added_pages = sorted(curr_urls - prev_urls)
    diff.removed_pages = sorted(prev_urls - curr_urls)

    # Bucket by structural fingerprint rather than a flat dict: multiple
    # distinct elements commonly share the same fingerprint (e.g. two
    # plain <button> elements on the same page with no test-id/name), and
    # a flat dict would silently drop all but one of them, causing
    # false-positive renames between unrelated elements. Buckets are
    # matched internally by text similarity instead.
    prev_buckets: dict[str, list[ElementModel]] = {}
    for e in previous.elements:
        prev_buckets.setdefault(_element_fingerprint(e), []).append(e)
    curr_buckets: dict[str, list[ElementModel]] = {}
    for e in current.elements:
        curr_buckets.setdefault(_element_fingerprint(e), []).append(e)

    matched_prev_ids: set[str] = set()
    matched_curr_ids: set[str] = set()

    all_fps = set(prev_buckets) | set(curr_buckets)
    for fp in all_fps:
        prev_group = list(prev_buckets.get(fp, []))
        curr_group = list(curr_buckets.get(fp, []))
        if not prev_group or not curr_group:
            continue  # entirely add or entirely remove for this bucket; handled below

        # Greedy best-first pairing within the bucket: prefer exact text
        # matches (truly unchanged elements), then highest text
        # similarity for the rest, so a same-fingerprint bucket with N
        # elements produces at most N pairs instead of one dict overwrite.
        remaining_curr = list(curr_group)
        for prev_el in prev_group:
            if not remaining_curr:
                break
            prev_text = (prev_el.text or prev_el.aria_label or "").strip()
            best_idx, best_score = None, -1.0
            for idx, curr_el in enumerate(remaining_curr):
                curr_text = (curr_el.text or curr_el.aria_label or "").strip()
                score = 100.0 if prev_text == curr_text else fuzz.ratio(prev_text, curr_text)
                if score > best_score:
                    best_score, best_idx = score, idx
            curr_el = remaining_curr.pop(best_idx)
            matched_prev_ids.add(prev_el.id)
            matched_curr_ids.add(curr_el.id)

            prev_text = (prev_el.text or prev_el.aria_label or "").strip()
            curr_text = (curr_el.text or curr_el.aria_label or "").strip()
            if prev_text != curr_text and prev_text and curr_text:
                diff.renamed_elements.append(
                    ElementChange(
                        change_type="RENAMED",
                        element_id_before=prev_el.id,
                        element_id_after=curr_el.id,
                        before=prev_el.model_dump(mode="json"),
                        after=curr_el.model_dump(mode="json"),
                        detail=f"Label changed from {prev_text!r} to {curr_text!r}.",
                    )
                )
            elif prev_el.visible != curr_el.visible or prev_el.enabled != curr_el.enabled:
                diff.attribute_changes.append(
                    ElementChange(
                        change_type="ATTRIBUTE_CHANGED",
                        element_id_before=prev_el.id,
                        element_id_after=curr_el.id,
                        before=prev_el.model_dump(mode="json"),
                        after=curr_el.model_dump(mode="json"),
                        detail="Visibility or enabled state changed.",
                    )
                )

    # Remaining unmatched elements (different fingerprint on both sides,
    # or leftover count within a bucket): try fuzzy structural+text match
    # to catch renames where a stable attribute (e.g. test-id) ALSO
    # changed; otherwise treat as pure add/remove.
    unmatched_prev = [e for e in previous.elements if e.id not in matched_prev_ids]
    unmatched_curr = [e for e in current.elements if e.id not in matched_curr_ids]

    used_curr_ids: set[str] = set()
    for prev_el in unmatched_prev:
        best_match = None
        best_score = 0.0
        for curr_el in unmatched_curr:
            if curr_el.id in used_curr_ids or curr_el.tag != prev_el.tag or curr_el.page_url != prev_el.page_url:
                continue
            score = fuzz.token_sort_ratio(
                (prev_el.text or prev_el.aria_label or ""), (curr_el.text or curr_el.aria_label or "")
            )
            if score > best_score:
                best_score = score
                best_match = curr_el
        if best_match is not None and best_score >= _RENAME_SIMILARITY_THRESHOLD:
            used_curr_ids.add(best_match.id)
            diff.renamed_elements.append(
                ElementChange(
                    change_type="RENAMED",
                    element_id_before=prev_el.id,
                    element_id_after=best_match.id,
                    before=prev_el.model_dump(mode="json"),
                    after=best_match.model_dump(mode="json"),
                    detail=(
                        f"Element re-identified after structural change: "
                        f"{(prev_el.text or prev_el.aria_label)!r} -> "
                        f"{(best_match.text or best_match.aria_label)!r}."
                    ),
                )
            )
        else:
            diff.removed_elements.append(
                ElementChange(
                    change_type="REMOVED",
                    element_id_before=prev_el.id,
                    element_id_after=None,
                    before=prev_el.model_dump(mode="json"),
                    after=None,
                    detail=f"Element {(prev_el.text or prev_el.aria_label or prev_el.tag)!r} no longer present.",
                )
            )

    for curr_el in unmatched_curr:
        if curr_el.id in used_curr_ids:
            continue
        diff.added_elements.append(
            ElementChange(
                change_type="ADDED",
                element_id_before=None,
                element_id_after=curr_el.id,
                before=None,
                after=curr_el.model_dump(mode="json"),
                detail=f"New element {(curr_el.text or curr_el.aria_label or curr_el.tag)!r} detected.",
            )
        )

    diff.added_forms = max(0, len(current.forms) - len(previous.forms))
    diff.removed_forms = max(0, len(previous.forms) - len(current.forms))
    diff.added_navigation = max(0, len(current.navigation) - len(previous.navigation))
    diff.removed_navigation = max(0, len(previous.navigation) - len(current.navigation))

    return diff
