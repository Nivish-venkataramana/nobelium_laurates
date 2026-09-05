# Security Model

## Threat model

This platform crawls and executes browser automation against
user-supplied URLs. Every target application is treated as **untrusted**
- both the content it serves (potential prompt injection into the AI
layer) and the network location it points to (potential SSRF against
internal infrastructure).

## SSRF / private-network protection

`app/core/security.py::validate_target_url` runs before any navigation,
for both the root URL and every same-domain link discovered during a
crawl:

- Only `http`/`https` schemes are allowed.
- The hostname is resolved via `socket.getaddrinfo` and every resolved
  address is checked against the private/reserved ranges: `127.0.0.0/8`,
  `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, `169.254.0.0/16`,
  `::1/128`, `fc00::/7`, `fe80::/10`, plus `0.0.0.0/8` and multicast/
  reserved addresses.
- `localhost` is blocked by default (needed for local demo use, so
  `ALLOW_PRIVATE_NETWORK_TARGETS=true` is provided specifically for
  running against the bundled `demo-app` in development).
- An optional `ALLOWED_DOMAINS` allowlist restricts crawling to a
  specific set of domains in stricter deployments.
- **Redirect protection**: after each navigation, the crawler checks
  `page.url` against the original domain; if a server redirects to a
  different host, the response is discarded and never extracted from.
  This is the practical mitigation against DNS-rebinding-style attacks,
  since the check happens against the address actually used for the
  connection, not just the pre-resolution hostname.

## Prompt injection

See `docs/ai-system.md`. Every prompt separates SYSTEM INSTRUCTIONS from
APPLICATION DATA from TASK, and the system prompt explicitly instructs
the model to treat page content as inert data regardless of its
phrasing. No secrets are ever interpolated into a prompt.

## No arbitrary code execution

- The AI can only emit actions from a fixed allowlist (`goto`, `click`,
  `fill`, `type`, `select`, `check`, `uncheck`, `hover`, `press`,
  `wait`, `screenshot`) and assertions from a fixed allowlist
  (`visible`, `hidden`, `text`, `url`, `value`, `attribute`, `count`).
  This is enforced at the Pydantic schema level
  (`app/schemas/test_case.py`), not just by convention.
- Every free-text value (fill/type values, assertion expected values) is
  scanned for code/shell-injection patterns (`import os`, `eval(`,
  `<script`, `os.system`, `rm -rf`, `curl `, `&& sh`, etc.) and rejected
  if found.
- The execution engines (`playwright_engine.py`, `selenium_engine.py`)
  only ever call a small, fixed set of Playwright/Selenium API methods
  corresponding to the allowlisted actions - there is no code path that
  evaluates a string as Python or JavaScript on the AI's behalf.

## Rate limiting and request size

`app/main.py` implements an in-memory per-IP sliding-window rate limiter
(`RATE_LIMIT_PER_MINUTE`, default 60/min) and rejects request bodies
larger than `MAX_REQUEST_BODY_BYTES` (default 2MB) before they reach any
handler. For a multi-instance production deployment, replace the
in-memory limiter with a Redis-backed one (the codebase already depends
on Redis for Celery, so this is a natural extension).

## Authentication

An API-key dependency (`app.api.dependencies.verify_api_key`) is wired
into the dependency-injection graph but is a no-op unless an `API_KEY`
environment variable is set, so local/demo use works without extra
setup. Production deployments should set `API_KEY` and/or replace this
with a full identity provider integration (OAuth2/OIDC) - the seam is
intentionally isolated to one function.

## Audit logging

The `audit_logs` table (`app/models/audit_log.py`) is designed to record
actor, action, resource type/id, and request-id for any
sensitive/state-changing operation. Structured logging
(`app/core/logging.py`) redacts any field whose key matches a sensitive
pattern (`api_key`, `password`, `token`, `cookie`, `authorization`,
`secret`, etc.) before it is ever written to a log line.

## Data retention

Retention windows for screenshots, traces, AI requests, and application
snapshots are configurable (`RETENTION_*_DAYS` in `.env.example`).
Sensitive page content is not retained indefinitely by default.
