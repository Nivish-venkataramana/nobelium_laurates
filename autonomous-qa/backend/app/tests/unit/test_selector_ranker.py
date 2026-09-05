from app.services.healing.candidate_finder import HealingCandidate
from app.services.healing.confidence import decide
from app.services.healing.selector_ranker import rank_candidates


def test_login_to_sign_in_is_the_top_candidate_and_clears_threshold(element_factory):
    original = element_factory("el_1", "button", "Login", role="button")
    candidates = [
        HealingCandidate(element=element_factory("el_2", "button", "Sign In", role="button")),
        HealingCandidate(element=element_factory("el_3", "a", "Help", role="link")),
        HealingCandidate(element=element_factory("el_4", "button", "Register", role="button")),
    ]

    ranked = rank_candidates(original, candidates)

    assert ranked[0].candidate.element.text == "Sign In"
    assert ranked[0].confidence > ranked[1].confidence

    decision = decide(ranked)
    assert decision.outcome == "HEAL"
    assert decision.best is not None
    assert decision.best.candidate.element.text == "Sign In"


def test_unrelated_candidates_do_not_clear_threshold(element_factory):
    original = element_factory("el_1", "button", "Delete Account", role="button")
    candidates = [HealingCandidate(element=element_factory("el_2", "button", "Contact Us", role="button"))]

    ranked = rank_candidates(original, candidates)
    decision = decide(ranked)

    assert decision.outcome == "REVIEW_REQUIRED"


def test_no_candidates_returns_no_candidates_outcome():
    decision = decide([])
    assert decision.outcome == "NO_CANDIDATES"
    assert decision.best is None


def test_exact_text_match_scores_highest_possible(element_factory):
    original = element_factory("el_1", "button", "Submit", role="button")
    candidates = [HealingCandidate(element=element_factory("el_2", "button", "Submit", role="button"))]

    ranked = rank_candidates(original, candidates)
    # An exact duplicate label should clear the healing confidence
    # threshold with room to spare, even though attribute overlap is
    # neutral (no test-id/name present on either element).
    assert ranked[0].confidence > 0.85
