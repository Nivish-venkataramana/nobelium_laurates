# Self-Healing

## Why this exists

A test step's locator can fail for a completely benign reason: a button
was relabeled, moved, or restructured while the underlying business
capability (e.g. "log in") is unchanged. Traditional automation treats
this as a broken test that needs a human to fix. This platform instead
treats it as a *change to understand and adapt to*.

## The pipeline

```
Step locator fails to resolve
        |
        v
Deterministic candidate discovery
   (extract every visible, interactive element currently on the page -
    the same extraction the discovery crawler uses, so candidates are
    always real, present elements, never invented)
        |
        v
Deterministic scoring (per candidate)
   role_match           x 0.25
   text_similarity      x 0.25
   semantic_similarity  x 0.20   (recognizes "Login" ~ "Sign In" via a
                                  small explicit synonym table, plus
                                  fuzzy token matching as a fallback)
   structure            x 0.15   (tag / input-type match)
   attributes           x 0.15   (name / placeholder / test-id overlap)
        |
        v
   confidence >= HEALING_CONFIDENCE_THRESHOLD (default 0.85)?
        |                                  |
       yes                                 no
        |                                  |
        v                                  v
     HEAL                    Is HEALING_LLM_FALLBACK_ENABLED and is the
   (deterministic)           top deterministic score at least plausible
                             (>= 0.35)?
                                      |
                                     yes
                                      |
                                      v
                          Ask the LLM to pick from the SAME
                          deterministically-scored candidate list
                                      |
                                      v
                          Independently re-check: is THAT candidate's
                          OWN deterministic score high enough?
                             (the LLM's self-reported confidence is
                              never trusted directly)
                                  |         |
                                 yes        no
                                  |         |
                                  v         v
                          HEAL            REVIEW_REQUIRED
                        (ai_assisted)
```

If no candidate clears the bar by either path, the step fails and the
event is recorded as `REVIEW_REQUIRED` - the platform never silently
guesses when confidence is low.

## Verification (retest)

Healing is never considered successful just because a candidate scored
well. After a repair is applied:

1. The repaired locator is used to complete the *same* step.
2. Execution continues through the rest of the test.
3. All assertions still have to pass.

Only if the whole test subsequently passes is the `HealingEvent`
recorded with outcome `HEALED`. If the test still fails afterward
(e.g. the repaired element wasn't actually the right one, or a
different problem exists), the event is recorded as `HEALING_FAILED`,
never `HEALED` - the record always reflects what was actually verified,
not what was attempted.

## What gets stored

Every attempt - successful, failed, or requiring review - is persisted
in `healing_events`: the original locator, the replacement locator (if
any), every candidate considered with its full score breakdown, the
confidence, the method (`deterministic` or `ai_assisted`), a
human-readable reason, the outcome, and the verification result. This
is what powers the Healing History page and the per-test healing
timeline in the UI.

## The demo scenario

The bundled demo app's login button has no `data-testid`, `name`, or
stable `id` - only a role (`button`) and visible text that toggles
between "Login" and "Sign In" via the `LOGIN_LABEL` environment
variable. This is deliberately the hardest realistic case: the only way
to recognize the two versions as "the same control" is role + semantic
label similarity, which is exactly what the deterministic scorer is
built to do. Verified in `app/tests/unit/test_selector_ranker.py` and
end-to-end in `app/tests/e2e/test_self_healing_e2e.py`.
