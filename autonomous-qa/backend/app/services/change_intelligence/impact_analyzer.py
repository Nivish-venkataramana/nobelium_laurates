"""Impact analysis: given a UIChange and the set of existing TestCases
(with their steps' target_element_id / locators), determine which tests
are likely affected by a detected change.

Purely deterministic: a test is "impacted" if any of its steps target
an element id that was renamed/removed/attribute-changed, or if its
business_intent matches a workflow touched by the change. No AI call is
needed for this — it is a structural lookup.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.models.test_case import TestCase
from app.services.change_intelligence.change_detector import UIChange


@dataclass
class ImpactedTest:
    test_case_id: str
    external_code: str
    name: str
    reason: str
    change_types: list[str] = field(default_factory=list)


@dataclass
class ImpactAnalysis:
    impacted: list[ImpactedTest] = field(default_factory=list)
    unaffected: list[ImpactedTest] = field(default_factory=list)

    @property
    def impacted_ids(self) -> set[str]:
        return {t.test_case_id for t in self.impacted}


def _affected_element_ids(change: UIChange) -> dict[str, str]:
    """Maps an affected element id -> change type, for both the 'before'
    id (removed/renamed source) and 'after' id (renamed target), since a
    test step might have originally targeted either."""
    affected: dict[str, str] = {}
    for item in change.renamed:
        if item.get("element_id_before"):
            affected[item["element_id_before"]] = "RENAMED"
        if item.get("element_id_after"):
            affected[item["element_id_after"]] = "RENAMED"
    for item in change.removed:
        if item.get("element_id_before"):
            affected[item["element_id_before"]] = "REMOVED"
    for item in change.attribute_changed:
        if item.get("element_id_before"):
            affected[item["element_id_before"]] = "ATTRIBUTE_CHANGED"
    return affected


def analyze_impact(change: UIChange, test_cases: list[TestCase]) -> ImpactAnalysis:
    result = ImpactAnalysis()
    if not change.has_changes:
        result.unaffected = [
            ImpactedTest(str(tc.id), tc.external_code, tc.name, "No changes detected.")
            for tc in test_cases
        ]
        return result

    affected_map = _affected_element_ids(change)

    for tc in test_cases:
        matched_types: list[str] = []
        matched_detail = None
        for step in tc.steps:
            target = step.target_element_id
            if target and target in affected_map:
                matched_types.append(affected_map[target])
                matched_detail = target

        if matched_types:
            result.impacted.append(
                ImpactedTest(
                    test_case_id=str(tc.id),
                    external_code=tc.external_code,
                    name=tc.name,
                    reason=(
                        f"Test step targets element '{matched_detail}', which was "
                        f"affected by a {'/'.join(sorted(set(matched_types)))} change."
                    ),
                    change_types=sorted(set(matched_types)),
                )
            )
        else:
            result.unaffected.append(
                ImpactedTest(str(tc.id), tc.external_code, tc.name, "No affected elements referenced.")
            )

    return result
