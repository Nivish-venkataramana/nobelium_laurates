# AI System

## Provider abstraction

Every AI-backed service depends on `app.services.ai.provider.LLMProvider`,
an abstract class with three methods: `generate_test_plan`,
`analyze_failure`, and `suggest_healing`. `app.services.ai.groq_provider.
GroqProvider` is the only concrete implementation and the only file in
the codebase that imports the `groq` SDK. Adding a new provider (OpenAI,
Anthropic, a local model) means writing one new class that implements
the same three methods and pointing `AI_PROVIDER` at it in
`get_llm_provider()` - nothing else changes.

## The three AI operations

1. **`generate_test_plan`** - given the compact `ApplicationModel` (never
   the raw DOM), produce a JSON test plan covering smoke, functional,
   negative, validation, boundary, navigation, workflow, and regression
   categories.
2. **`analyze_failure`** - given a failure's evidence (error message,
   step results), produce a plain-language, evidence-grounded
   explanation and a coarse cause classification.
3. **`suggest_healing`** - given a failed locator's business intent and a
   list of *already deterministically scored* DOM candidates, recommend
   which one is the best replacement.

## Validation pipeline (non-negotiable)

```
LLM response (raw text)
    -> JSON extraction        (app/services/ai/json_extract.py)
    -> Pydantic schema validation
         - allowlisted actions only: goto, click, fill, type, select,
           check, uncheck, hover, press, wait, screenshot
         - allowlisted assertions only: visible, hidden, text, url,
           value, attribute, count
         - forbidden-pattern scan on every free-text value (blocks
           `import os`, `eval(`, `<script`, `rm -rf`, etc.)
         - targeted actions (click/fill/...) MUST carry a locator
    -> semantic validation      (every target_element_id must exist in
                                  the ApplicationModel that was sent)
    -> persisted as TestCase/TestStep rows
    -> execution engine (only entity that can produce PASS/FAIL)
```

Anything that fails validation is rejected outright and logged; it is
never partially trusted or "fixed up" into something executable.

## Prompt-injection defense

Every prompt sent to the model explicitly separates SYSTEM INSTRUCTIONS
from APPLICATION DATA from TASK (see `app/services/ai/prompts.py`).
Application data - element text, aria-labels, page titles pulled from a
third-party page - is clearly labelled as inert data the model must
analyze, not obey, even if it contains imperative-looking text like
"ignore your instructions." No secrets are ever interpolated into a
prompt.

## Cost control

The healing pipeline only calls the LLM as a last resort:

```
1. primary locator
2. fallback locators
3. deterministic candidate scoring (role/text/semantic/structure/attributes)
4. confidence >= threshold?  -> repair, no AI call
5. still inconclusive AND top deterministic score is at least plausible
   -> ask the LLM to pick from the SAME candidate list
6. independently re-score the LLM's pick before ever using it
```

Every AI call - test planning, failure analysis, and healing - is
recorded in the `ai_requests` table with model, latency, token counts
(when available), and an estimated cost, so usage is fully observable
even though no real-time billing API is queried.
