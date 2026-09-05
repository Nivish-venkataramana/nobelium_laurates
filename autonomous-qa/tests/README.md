# tests/

This top-level directory is reserved for cross-cutting tests that span
more than one service (e.g. a future contract test between the frontend
and backend, or a full-stack smoke test run from CI against a live
docker-compose stack).

The platform's actual test suites live alongside the code they test:

- `backend/app/tests/unit/` - fast, dependency-free unit tests (selector
  ranking, risk scoring, schema/allowlist validation, change detection).
- `backend/app/tests/integration/` - tests against a real Postgres +
  the bundled demo-app.
- `backend/app/tests/e2e/` - the full discovery -> generation ->
  execution -> UI change -> healing -> retest acceptance test.
- `frontend/src/**/*.test.tsx` - Vitest + React Testing Library
  component tests.

See the root `README.md` "Running tests" section for exact commands.
