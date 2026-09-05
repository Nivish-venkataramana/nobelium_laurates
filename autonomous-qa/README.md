# Autonomous Quality Engineering Platform

**AI that adapts QA as fast as software changes.**

## Core principle

```
AI PROPOSES.  AUTOMATION EXECUTES.  VERIFICATION DECIDES.
AI ANALYZES.  SELF-HEALING REPAIRS.  HISTORY LEARNS.
```

The LLM never decides pass/fail, never executes code directly, and
never applies its own healing suggestion without independent
verification. See [`docs/security.md`](docs/security.md) and
[`docs/ai-system.md`](docs/ai-system.md) for exactly how this is
enforced at the schema and execution-engine level.

## Problem

Traditional automated QA relies on static selectors and manually
maintained scripts. When an application's UI changes - even a harmless
relabel like "Login" to "Sign In" - hundreds of tests can break even
though the underlying business functionality is unchanged. This
platform moves from "maintain broken test scripts" to "understand
application behavior and automatically adapt quality validation."

## Lifecycle

```
OBSERVE -> UNDERSTAND -> DETECT CHANGE -> PREDICT IMPACT -> GENERATE TESTS
   -> EXECUTE -> ANALYZE -> HEAL -> RETEST -> LEARN -> EXPLAIN
```

## What's implemented

- **Discovery**: real Playwright-based crawling into a compact, semantic
  `ApplicationModel` (pages, elements, forms, navigation, inferred
  business-intent workflows) - never the raw DOM.
- **AI test planning**: Groq-backed generation of smoke/functional/
  negative/validation/boundary/navigation/workflow/regression tests,
  behind an `LLMProvider` abstraction, with a strict validation pipeline
  (JSON extraction -> schema -> semantic -> safety) before anything is
  persisted.
- **Execution**: a real `ExecutionEngine` abstraction with Playwright
  (primary) and Selenium (secondary) implementations sharing the same
  `TestDefinition` contract, a deterministic allowlisted action
  interpreter, and assertion evaluation.
- **Self-healing**: deterministic candidate scoring (role/text/semantic/
  structure/attributes) first, AI-assisted fallback second, always with
  independent re-verification before a repair is trusted. See
  [`docs/self-healing.md`](docs/self-healing.md).
- **Change intelligence**: snapshot diffing (added/removed/renamed/
  attribute-changed elements) and structural impact analysis mapping
  changes to affected tests.
- **Risk engine**: explainable, weighted scoring (business criticality,
  change magnitude, historical failure rate, security sensitivity,
  regression history) - never an opaque black-box number.
- **Quality score & explanations**: computed from real execution data;
  unsupported dimensions (accessibility, API health) show `N/A` rather
  than a fabricated number.
- **Full run state machine**, background execution via Celery/Redis so
  browser automation never blocks HTTP requests.
- **React/TypeScript/Vite/Tailwind dashboard**: Dashboard, Projects,
  Application detail, Discovery, Test Cases, Test Detail, Test Runs, Run
  Detail, Healing History, Settings.
- **Demo app** (Flask) with a `LOGIN_LABEL` toggle (`Login` / `Sign In`)
  used to demonstrate self-healing end-to-end, plus a genuine multi-page
  flow (Home, Login, Register, Products, Cart, Checkout, Contact).
- **Security**: SSRF/private-IP/localhost blocking with DNS resolution
  checks and redirect-escape protection, prompt-injection defense,
  code-injection pattern rejection, rate limiting, structured logging
  with secret redaction.

## What's intentionally an extension point, not a fake implementation

Per the platform's "no fake implementations" rule, the following have
real interfaces/abstractions ready to be filled in, but no
implementation: API testing (`APITestEngine`), unit-test generation,
security testing (`SecurityTestEngine`), accessibility testing
(`AccessibilityEngine`), performance testing (`PerformanceEngine`).
Building these out is straightforward given the existing
`ExecutionEngine`-style abstraction pattern, but implementing them was
out of scope for this initial build.

## Repository structure

```
autonomous-qa/
├── backend/            FastAPI + SQLAlchemy + Alembic + Celery
│   └── app/
│       ├── api/routes/         REST endpoints
│       ├── core/                config, logging, security, exceptions
│       ├── models/              SQLAlchemy tables
│       ├── schemas/             Pydantic v2 (safety allowlists live here)
│       ├── services/
│       │   ├── discovery/       Playwright crawler -> ApplicationModel
│       │   ├── ai/              LLMProvider abstraction + GroqProvider
│       │   ├── execution/       ExecutionEngine (Playwright/Selenium)
│       │   ├── healing/         self-healing pipeline
│       │   ├── change_intelligence/  snapshot diff + impact analysis
│       │   ├── risk/            explainable risk scoring
│       │   └── reporting/       quality score + explanations
│       ├── workers/             Celery app + orchestration task
│       ├── repositories/        DB access
│       └── tests/{unit,integration,e2e}
├── frontend/           React + TypeScript + Vite + Tailwind
├── demo-app/           Flask demo app (Login/Sign In toggle)
├── docs/               architecture, ai-system, self-healing, security, api
├── Makefile
└── Makefile
```

## Installation

**Prerequisites** (install via [Homebrew](https://brew.sh) if missing):

```bash
brew install python@3.12 node postgresql@16 redis
```

A Groq API key (https://console.groq.com) is required for AI test
generation, failure analysis, and AI-assisted healing to work; without
it, discovery and execution against manually-created test cases still
work, but `run_generation` will fail with a clear error.

```bash
git clone <this repo>
cd autonomous-qa
cp .env.example .env
# edit .env and set GROQ_API_KEY=...
```

## Starting the system

```bash
./start.sh
```

This script:
1. Starts PostgreSQL and Redis via Homebrew (if not already running)
2. Creates the `qa_user` role and `autonomous_qa` database if missing
3. Creates a Python venv in `backend/.venv` and installs all deps
4. Installs Playwright Chromium and frontend npm packages
5. Runs Alembic migrations
6. Launches backend, worker, frontend, and demo-app in the background

Service URLs:
- Frontend: http://localhost:5173
- Backend API docs: http://localhost:8000/docs
- Demo app: http://localhost:5050

Logs are written to `./logs/{backend,worker,frontend,demo-app}.log`.

## Stopping the system

```bash
./stop.sh
```

To also stop PostgreSQL and Redis:

```bash
brew services stop postgresql@16 redis
```

You can also use `make up` / `make down` for the same effect.

## Database migrations

Migrations run automatically when `./start.sh` is executed. To run
them manually:

```bash
make migrate
# or: cd backend && ../.venv/bin/alembic upgrade head
```

## Running tests

```bash
make test-backend    # pytest app/tests/unit (fast, no external deps)
make test-frontend   # vitest
```

Integration and end-to-end tests need the full stack running
(`./start.sh`) with the demo-app in `DEMO_MODE=true`:

```bash
cd backend && ../.venv/bin/pytest app/tests/integration -v
cd backend && ../.venv/bin/pytest app/tests/e2e -v
```

## Linting / type checking

```bash
make lint
make typecheck
```

## Using the dashboard

1. Open http://localhost:5173.
2. **Projects** -> create a project.
3. Inside the project, **add an application** pointing at
   `http://localhost:5050` (the demo-app address).
4. Go to **Discovery**, select the application, and run discovery to see
   the extracted `ApplicationModel` (pages/elements/forms/workflows).
5. From the application page, click **Discover + Generate + Run** to
   have Groq generate a test plan and execute it with Playwright.
6. Watch progress on the **Run Detail** page (polls automatically),
   inspect **Test Cases**, and check **Healing History** for any
   self-healing activity.

## Self-healing demo (the flagship scenario)

```bash
# 1. Confirm the demo app is running with the original label
make demo-a          # LOGIN_LABEL=Login

# 2. In the dashboard: create a project + application, discover, generate
#    tests via Groq, and run them. The login test should pass.

# 3. Flip the label to simulate a UI change
make demo-b          # LOGIN_LABEL=Sign In

# 4. Run discovery again from the dashboard. Change intelligence detects
#    the rename ("Login" -> "Sign In") and flags the login test as impacted.

# 5. Re-run the (now stale) login test. Its original locator fails;
#    the self-healing engine deterministically finds "Sign In" as the
#    replacement, verifies it by completing the login flow, and marks
#    the result HEALED. Check the Run Detail and Healing History pages.
```

This is also covered by an automated end-to-end test
(`backend/app/tests/e2e/test_self_healing_e2e.py`) that flips the demo
app's label via a test-only `/debug/set-login-label` endpoint (enabled
only when `DEMO_MODE=true`) and asserts the repaired test actually
passes - no step of the healing logic itself is hardcoded to this
scenario.

## Security model

See [`docs/security.md`](docs/security.md). Summary: every crawl/execution
target is treated as untrusted (SSRF and private-IP blocking, redirect-
escape protection), the AI layer has explicit prompt-injection defenses
and a hard allowlist of actions/assertions it may ever emit, and no
component ever executes AI-generated code or shell commands.

## AI safety

See [`docs/ai-system.md`](docs/ai-system.md). Summary: LLM output always
goes through JSON extraction -> schema validation -> semantic validation
-> safety validation before it can affect a test run, and the LLM
never gets to decide pass/fail or apply its own healing suggestion
without independent re-verification.

## Production deployment notes

This build is optimized for local/demo use. Before a production
deployment, consider:

- Replacing the in-memory rate limiter with a Redis-backed one.
- Adding a real identity provider (OAuth2/OIDC) behind the
  `verify_api_key` dependency seam.
- Running Celery with a process supervisor and horizontal worker scaling
  tied to `MAX_CONCURRENT_BROWSER_CONTEXTS`.
- Wiring up the data-retention settings to a scheduled cleanup job
  (models/columns already support it; no scheduler is included).
- Turning on `mypy` as a blocking CI step once type coverage is complete
  (currently non-blocking in CI).

## Future roadmap

API testing, unit-test generation, security testing, accessibility
testing, and performance testing all have extension-point interfaces
ready (see Architecture doc) but no implementation yet. Flaky-test
detection and advanced regression intelligence can build directly on
the existing `test_results` history. Multi-browser testing is a
matter of adding Firefox/WebKit launch options to `PlaywrightEngine`.
