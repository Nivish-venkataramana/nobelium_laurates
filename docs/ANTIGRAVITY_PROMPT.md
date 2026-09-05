# Master Build Prompt — AegisQA

Paste everything below this line into Antigravity (or Claude Code) as the
task. It is written to be executed phase-by-phase with a checkpoint after
each phase, rather than in one uninterrupted generation pass — this
produces more reliable code and lets you course-correct early.

---

## SYSTEM ROLE

You are an expert Systems Architect and Autonomous QA Engineer building
**AegisQA** — an AI-powered autonomous Quality Engineering companion — for
the hackathon problem statement:

> "Autonomous Quality Engineering for the AI Development Era."

## PROBLEM THIS SOLVES

AI code generators (Copilot, Cursor, v0, etc.) constantly rewrite DOM
structure — IDs, class names, and element hierarchy shift on every commit.
Traditional Selenium/Playwright tests built on CSS/XPath selectors break
on every such change. AegisQA replaces selector-based testing with
**"Intent-Invariant Autonomous Testing"**: it anchors tests to the
accessibility tree (roles, accessible names, states) instead of DOM shape,
and when a locator still breaks, it heals itself at runtime using Groq
inference — fast enough to happen mid-demo without visibly stalling.

## NON-NEGOTIABLE CONSTRAINTS

1. **No Docker, no k8s.** Every component is a native Python 3.11+
   process. If you are about to write a Dockerfile or docker-compose.yml,
   stop — that's the wrong direction.
2. **No heavy frameworks.** SQLite for persistence, Playwright's own
   binaries for browser automation, Streamlit for the UI, `rich`/`typer`
   for the CLI. Do not introduce Redis, Celery, Postgres, or a JS frontend
   build step.
3. **Groq for inference**, via the official `groq` Python SDK:
   - `llama-3.1-8b-instant` for `core/healer.py` (latency-critical —
     must resolve well under `HEALER_TIMEOUT_MS`, default 300ms).
   - `llama-3.3-70b-versatile` for `core/intent_engine.py` workflow
     synthesis and `monitors/log_watcher.py` anomaly classification
     (not latency-critical — correctness matters more than speed here).
4. **Every module reads config from `config/settings.py` only.** No
   `os.environ.get(...)` calls scattered through the codebase.
5. **Data contracts are fixed.** Use the exact JSON shapes in
   `docs/SCHEMAS.md` for CrawlGraph, Workflow, HealEvent, Finding,
   RequestMetric, and LogAnomaly. If a phase genuinely requires changing
   a schema, update `docs/SCHEMAS.md` in the same commit and say so
   explicitly in your summary — don't silently drift from it.

## REPOSITORY LAYOUT (already scaffolded — do not restructure it)

```
config/settings.py
core/{crawler,intent_engine,healer}.py
runners/{ui_runner,security_scanner,perf_monitor}.py
monitors/log_watcher.py
dashboard/app.py
tests/sample_app/app.py
tests/generated_specs/            (generated specs land here at runtime)
storage/test_runs.db              (created at runtime, git-ignored)
main.py
requirements.txt
docs/SCHEMAS.md
```

Every file above currently contains a docstring stub describing its exact
responsibility and expected interface. **Read the existing stub in a file
before rewriting it** — the stub is the spec for that file; implement
against it rather than re-deriving the design from scratch.

## HOW TO WORK: PHASE GATES

Implement the phases below **in order**. After each phase, stop and:
(a) list the files you created/changed, (b) state how to manually verify
the phase worked, (c) wait for confirmation before continuing — unless
explicitly told to run all phases unattended.

### Phase 1 — Foundations
- Implement `config/settings.py` as a `pydantic-settings` `BaseSettings`
  class per its stub. Load from `.env` (see `.env.example`).
- Implement `requirements.txt` if any dependency is missing (it already
  lists the expected set — add anything you actually import).
- **Acceptance check:** `python -c "from config.settings import settings; print(settings.GROQ_MODEL_FAST)"`
  prints the model name without raising, given a `.env` with a dummy
  `GROQ_API_KEY`.

### Phase 2 — Demo target app
- Implement `tests/sample_app/app.py` per its stub: a login → cart →
  checkout flow, an `APP_VERSION=v1|v2` toggle that changes the checkout
  button's tag/id/class while keeping its accessible role+name identical,
  and one deliberately-reflective input field for the security scanner to
  catch.
- **Acceptance check:** `python tests/sample_app/app.py` serves on
  `SAMPLE_APP_PORT`; toggling `APP_VERSION` changes the rendered HTML for
  the checkout control but not its accessible name (verify by eye — view
  source on both versions).

### Phase 3 — Discovery, synthesis, healing (the core IP)
- Implement `core/crawler.py`, `core/intent_engine.py`, `core/healer.py`
  per their stubs and `docs/SCHEMAS.md`.
- Write the generated Playwright specs to `tests/generated_specs/` using
  `get_by_role` / `get_by_label` / `get_by_text` locators — never raw
  CSS/XPath — so `core/healer.py` has a stable intent to recover when
  these still fail after a redesign.
- **Acceptance check:** `python main.py crawl http://localhost:5000`
  (with the Phase 2 app running) prints/saves a CrawlGraph with at least
  the login, cart, and checkout pages and their interactive elements.

### Phase 4 — Execution, security, performance
- Implement `runners/ui_runner.py`, `runners/security_scanner.py`,
  `runners/perf_monitor.py` per their stubs.
- Create `storage/db.py`: a single SQLite helper module (schema per
  `docs/SCHEMAS.md`'s table list) that every runner writes through — no
  ad-hoc `sqlite3.connect()` calls elsewhere.
- **Acceptance check:** run the full flow against the Phase 2 app on
  `APP_VERSION=v1` — it passes with zero heals. Switch to `APP_VERSION=v2`
  without regenerating the spec, re-run — the checkout step's locator
  fails, `core/healer.py` resolves a replacement in under
  `HEALER_TIMEOUT_MS * 3` (allow slack for a cold Groq call) and the run
  still ends in "passed" with a heal event recorded.

### Phase 5 — Backend log correlation
- Implement `monitors/log_watcher.py` per its stub. Make
  `tests/sample_app/app.py` (Phase 2) write to `LOG_WATCH_PATH` if it
  doesn't already.
- **Acceptance check:** manually append a fake stack trace line to the
  log file while the watcher is running; confirm it's classified and
  shows up as a LogAnomaly (print it to console is fine for this check).

### Phase 6 — Dashboard
- Implement `dashboard/app.py` per its stub, reading only through
  `storage/db.py`. Live-update the step stream during a run (Streamlit's
  `st.empty()`/rerun patterns, or a background thread writing to session
  state — your choice, but it must update *during* the run, not only
  after it finishes).
- **Acceptance check:** `streamlit run dashboard/app.py`, click "Start
  Autonomous Test" against the running sample app, watch steps stream in
  live, and see a "Locator Healed" indicator appear when run against
  `APP_VERSION=v2`.

### Phase 7 — CLI glue
- Implement `main.py` with the four subcommands in its stub
  (`crawl`, `run`, `dashboard`, `demo`). `demo` should start the sample
  app and the dashboard together (subprocess or threads) so the whole
  thing is a single command for the judges.
- **Acceptance check:** `python main.py demo` brings up both processes
  and prints the URLs to open.

## DEMO SCRIPT TO OPTIMIZE FOR

The judges will watch this sequence — make sure it works reliably, not
just once in development:

1. Run AegisQA against the sample app on **v1**. Narrate: crawler
   discovers elements, workflow executes, latency is logged.
2. Toggle the sample app to **v2** live (button's tag/id/class changes,
   accessible role/name doesn't).
3. Re-run the *same, unmodified* generated spec. It should hit the
   missing locator, pause briefly, heal via Groq, and pass — with the
   dashboard flashing the heal event and its latency.
4. Point at the correlated report: the security scanner's XSS finding on
   the vulnerable field, and clean backend log health, from that same
   run.

## WHAT "DONE" LOOKS LIKE

- No stub docstrings remain unimplemented (or, if a stretch feature is
  intentionally skipped, its stub says so with a one-line reason).
- `docs/SCHEMAS.md` still accurately describes every JSON shape actually
  produced.
- The Phase 4 acceptance check (v1 passes clean, v2 heals and still
  passes) works on a fresh clone with only `.env` filled in.
- `python main.py demo` is the single command that gets a judge from
  nothing to the full live demo.

## START HERE

Begin with Phase 1. Do not skip ahead to the dashboard or CLI before the
crawler/intent/healer core (Phase 3) is real — that core is the entire
point of this project; everything else is presentation around it.
