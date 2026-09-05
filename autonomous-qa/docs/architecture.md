# Architecture

## Design principle

The platform enforces one rule above all others: **the LLM proposes,
deterministic engines decide.** Concretely:

- The LLM can produce a test *plan* (JSON), a *suggestion* for which
  locator to try during healing, and a plain-language *explanation* of a
  failure.
- The LLM can never mark a test PASSED, execute code, run shell
  commands, touch the database directly, or apply its own healing
  suggestion. Every one of those steps runs through a schema-validated,
  deterministic pipeline first.

This shows up everywhere in the codebase: `app/schemas/test_case.py`
enforces an allowlist of actions/assertions the AI is permitted to
emit; `app/services/execution/action_interpreter.py` is the *only*
place that turns validated data into a real Playwright call;
`app/services/healing/healer.py` always independently re-scores an
AI-suggested healing candidate against the same deterministic ranking
used for the non-AI path before it is ever applied.

## Request flow

```
React frontend
     |  REST (JSON)
     v
FastAPI (app/main.py)
     |  synchronous CRUD (projects/applications/tests) -> Postgres directly
     |  discovery (fast) -> runs inline in the request (async Playwright)
     |  runs (slow: generation + execution + healing) -> enqueued to Celery
     v
Celery worker (app/workers/tasks.py)
     v
Orchestrator (app/services/execution/orchestrator.py)
     OBSERVE (discovery) -> UNDERSTAND (ApplicationModel) ->
     DETECT CHANGE (snapshot diff) -> PREDICT IMPACT (impact analysis) ->
     GENERATE TESTS (AI + validation) -> EXECUTE (Playwright/Selenium) ->
     ANALYZE (AI failure explanation) -> HEAL (deterministic -> AI-assisted) ->
     RETEST (same engine, repaired locator) -> LEARN (risk + quality score) ->
     EXPLAIN (evidence-based summary)
```

## Layering

- **`api/`** - FastAPI routers. Thin: parse request, call a
  repository/service, return a schema. No business logic lives here.
- **`schemas/`** - Pydantic v2 models. This is where the safety
  allowlist for AI-generated content is enforced (see
  `schemas/test_case.py`).
- **`models/`** - SQLAlchemy ORM tables.
- **`repositories/`** - thin DB-access functions, one per aggregate
  (projects, applications, test_cases, runs). Keeps SQLAlchemy query
  construction out of the API and service layers.
- **`services/discovery/`** - Playwright crawler -> DOM extraction ->
  locator construction -> canonical `ApplicationModel`.
- **`services/ai/`** - the `LLMProvider` abstraction, the `GroqProvider`
  implementation (the only file that imports the `groq` SDK), prompt
  templates, and the JSON-extraction + validation pipeline.
- **`services/execution/`** - the `ExecutionEngine` abstraction, the
  Playwright and Selenium implementations, the deterministic action
  interpreter and assertion evaluator, and the orchestrator that ties
  the whole pipeline together for one `TestRun`.
- **`services/healing/`** - candidate discovery, deterministic
  confidence scoring, AI-assisted fallback, and the confidence-threshold
  policy.
- **`services/change_intelligence/`** - snapshot diffing and impact
  analysis.
- **`services/risk/`** - the explainable risk scorer.
- **`services/reporting/`** - quality score computation and
  evidence-grounded explanation assembly.
- **`workers/`** - Celery app + the task that runs `run_pipeline`
  inside a worker process (never inside an HTTP request thread).

## Why Celery for runs but not for discovery

A single discovery call opens one browser context for a few seconds -
short enough to run as a normal `async def` FastAPI route without
blocking other requests' event loop, since Playwright's async API
yields control during I/O. A full run (discovery + AI generation +
N test executions + healing) can take minutes, so it is handed to a
Celery worker immediately and the API returns `{"run_id", "status":
"QUEUED"}`.

## Extension points (not implemented, deliberately)

Per the product spec, several future capabilities have real
abstractions/interfaces but no implementation, so they can be added
without restructuring anything:

- `APITestEngine` (contract/API testing)
- `SecurityTestEngine` (header/auth checks)
- `AccessibilityEngine` (axe-core integration)
- `PerformanceEngine` (Core Web Vitals, navigation timing)
- Unit-test generation (source code -> AI -> pytest/Jest/JUnit)

These are intentionally left as extension points rather than stubbed
with fake results, per the platform's "no fake implementations" rule.
