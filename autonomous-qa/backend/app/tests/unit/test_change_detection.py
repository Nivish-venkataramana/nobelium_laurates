from app.schemas.discovery import ApplicationMeta, ApplicationModel, PageModel
from app.services.change_intelligence.change_detector import detect_change
from app.services.change_intelligence.impact_analyzer import analyze_impact
from app.services.change_intelligence.snapshot_comparator import compare_snapshots


def _model(elements, page_url="http://demo/login"):
    return ApplicationModel(
        application=ApplicationMeta(url="http://demo", title="Demo"),
        pages=[PageModel(url=page_url, title="Login", element_ids=[e.id for e in elements])],
        elements=elements,
    )


def test_renamed_element_is_detected(element_factory):
    before = _model([element_factory("el_1", "button", "Login", role="button")])
    after = _model([element_factory("el_1", "button", "Sign In", role="button")])

    diff = compare_snapshots(before, after)
    change = detect_change(diff)

    assert change.has_changes
    assert len(change.renamed) == 1
    assert change.renamed[0]["element_id_before"] == "el_1"


def test_no_changes_when_snapshots_identical(element_factory):
    model = _model([element_factory("el_1", "button", "Login", role="button")])
    diff = compare_snapshots(model, model)
    change = detect_change(diff)
    assert not change.has_changes


def test_added_and_removed_elements_detected(element_factory):
    before = _model([element_factory("el_1", "button", "Login", role="button")])
    after = _model(
        [
            element_factory("el_1", "button", "Login", role="button"),
            element_factory("el_2", "button", "Forgot Password", role="button"),
        ]
    )
    diff = compare_snapshots(before, after)
    change = detect_change(diff)
    assert len(change.added) == 1


class _FakeStep:
    def __init__(self, target_element_id):
        self.target_element_id = target_element_id


class _FakeTestCase:
    def __init__(self, id, external_code, name, steps):
        self.id = id
        self.external_code = external_code
        self.name = name
        self.steps = steps


def test_impact_analysis_flags_tests_referencing_renamed_element(element_factory):
    before = _model([element_factory("el_1", "button", "Login", role="button")])
    after = _model([element_factory("el_1", "button", "Sign In", role="button")])
    diff = compare_snapshots(before, after)
    change = detect_change(diff)

    login_test = _FakeTestCase("t1", "TC001", "Login Test", [_FakeStep("el_1")])
    other_test = _FakeTestCase("t2", "TC002", "Unrelated Test", [_FakeStep("el_999")])

    impact = analyze_impact(change, [login_test, other_test])

    assert "t1" in impact.impacted_ids
    assert "t2" not in impact.impacted_ids
