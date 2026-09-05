# AegisQA

**Autonomous Quality Engineering for the AI Development Era**

AegisQA is an AI-powered autonomous QA companion that replaces selector-based Playwright tests with *Intent-Invariant Autonomous Testing*. It anchors tests to the **accessibility tree** (roles, accessible names, states) instead of DOM shape — and when a locator still breaks, it **heals itself at runtime** using Groq inference in under 300 ms.

---

## Why AegisQA?

AI code generators (Copilot, Cursor, v0) constantly rewrite DOM structure — IDs, class names, and element hierarchy shift on every commit. Traditional Selenium/Playwright tests built on CSS/XPath selectors break on every such change.

AegisQA survives this because it:
- **Crawls** the app's ARIA accessibility tree, not the DOM
- **Synthesises** workflows from accessibility intent using Groq LLMs
- **Heals** failing locators in < 300 ms at runtime (Groq `llama-3.1-8b-instant`)
- **Scans** for XSS/injection reflection automatically
- **Correlates** backend log anomalies with test steps in real time
- **Streams** everything live to a Streamlit dashboard

---

## Architecture

```
main.py (typer CLI)
  ├── crawl  → core/Crawler      → ARIA tree (CrawlGraph)
  ├── run    → core/IntentEngine  → Workflow JSON
  │            → runners/UIRunner → step execution
  │                 ├── core/Healer          (Groq llama-3.1-8b-instant, < 300 ms)
  │                 ├── runners/PerfMonitor  (network latency flags)
  │                 └── runners/SecurityScanner (OWASP XSS probes)
  ├── dashboard → streamlit run dashboard/app.py
  └── demo      → sample app + dashboard together (judge-ready)

monitors/LogWatcher  → daemon thread, tails LOG_WATCH_PATH, classifies via Groq
storage/db.py        → single SQLite connection (WAL mode, 6 tables)
```

---

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
python -m playwright install chromium
```

### 2. Configure

```bash
copy .env.example .env
```

Edit `.env` and set your **Groq API key**:
```
GROQ_API_KEY=gsk_your_key_here
```

Get a free key at https://console.groq.com

### 3. Run the demo (single command — judge-ready)

```bash
python main.py demo
```

This starts:
- **Sample App** at `http://localhost:5000` (APP_VERSION=v1)
- **Dashboard** at `http://localhost:8501`

Open the dashboard URL, click **Start Autonomous Test**, and watch the live stream.

---

## Proving Self-Healing (v1 → v2)

```bash
# Terminal 1: run v1 (all steps pass, 0 heals)
python main.py run http://localhost:5000

# Restart sample app as v2 (DOM structure changes completely)
set APP_VERSION=v2
python tests/sample_app/app.py

# Terminal 2: run SAME spec against v2 (checkout step HEALS automatically)
python main.py run http://localhost:5000
```

Watch the `HEALED` line — it shows the old locator, the healed locator, and the Groq inference latency in ms.

---

## CLI Reference

```
python main.py --help

Commands:
  crawl      Crawl a URL and print its accessibility-tree graph
  run        Full run: crawl → synthesise → execute → security scan → report
  dashboard  Launch the Streamlit live dashboard
  demo       Start sample app + dashboard together (judge mode)
```

### Environment Variables (`.env`)

| Variable | Default | Description |
|----------|---------|-------------|
| `GROQ_API_KEY` | *required* | Groq API key |
| `GROQ_MODEL_FAST` | `llama-3.1-8b-instant` | Healer + log classifier |
| `GROQ_MODEL_REASONING` | `llama-3.3-70b-versatile` | Workflow synthesis |
| `HEALER_TIMEOUT_MS` | `300` | Hard wall-clock limit for healer Groq call |
| `CRAWLER_MAX_DEPTH` | `3` | BFS link-follow depth |
| `CRAWLER_MAX_PAGES` | `25` | Max pages per crawl |
| `TARGET_BASE_URL` | `http://localhost:5000` | Default target for `run` |
| `SAMPLE_APP_PORT` | `5000` | Port for the demo sample app |
| `DASHBOARD_PORT` | `8501` | Streamlit dashboard port |
| `SQLITE_PATH` | `storage/test_runs.db` | SQLite database location |
| `LOG_WATCH_PATH` | `storage/app.log` | Log file tailed by LogWatcher |
| `OWASP_PAYLOAD_SET` | `standard` | `standard` or `extended` XSS payloads |

---

## Demo App: The v1/v2 Mutation

The sample app at `tests/sample_app/app.py` ships two checkout-button DOM shapes:

| | v1 | v2 |
|---|---|---|
| Tag | `<button>` | `<a>` |
| `id` | `checkout-btn` | *(none)* |
| `class` | *(none)* | `tw-bg-blue-500 tw-btn` |
| `role` | *(implicit button)* | `role="button"` |
| `aria-label` | `Checkout` | `Checkout` |
| Text | `Checkout` | `Continue to Pay` |

Traditional XPath/CSS selector-based tests break on v2. AegisQA's healer finds the element via `aria-label="Checkout"` and continues.

The promo code field echoes its value unescaped into the HTML — a deliberate XSS reflection surface for the security scanner.

---

## Acceptance Checks

```bash
# Phase 1: settings load
python -c "from config.settings import settings; print(settings.GROQ_MODEL_FAST)"
# → llama-3.1-8b-instant

# Phase 2: sample app renders both versions
python tests/sample_app/app.py   # then curl http://localhost:5000/checkout

# Phase 3: crawler
python main.py crawl http://localhost:5000

# Phase 4: full run (v1 — all pass, 0 heals)
python smoke_v1.py

# Phase 4: full run (v2 — checkout heals, needs real GROQ_API_KEY)
# [restart app with APP_VERSION=v2]
python smoke_v2.py

# Phase 5: log watcher
# With app running, append a fake traceback:
Add-Content -Path storage/app.log -Value "ERROR NullPointerException at checkout_handler`nTraceback (most recent call last):`n  File app.py line 42`n"
# Check dashboard Backend Log Health panel for anomaly alert
```

---

## Project Structure

```
aegis-qa/
├── config/settings.py          # All config via pydantic-settings
├── core/
│   ├── crawler.py              # ARIA-tree BFS crawler (Playwright)
│   ├── intent_engine.py        # Workflow synthesis (Groq reasoning model)
│   └── healer.py               # Self-healing locator resolver (Groq fast model)
├── runners/
│   ├── ui_runner.py            # Workflow executor with heal-on-fail
│   ├── security_scanner.py     # OWASP XSS/reflection scanner
│   └── perf_monitor.py         # Network latency & anomaly monitor
├── monitors/
│   └── log_watcher.py          # Live log tail + Groq anomaly classifier
├── dashboard/app.py            # Streamlit live control room
├── storage/
│   └── db.py                   # SQLite helper (6 tables, WAL mode)
├── tests/sample_app/app.py     # Flask demo target (v1/v2 toggle + XSS surface)
├── main.py                     # typer CLI (crawl/run/dashboard/demo)
├── smoke_v1.py                 # Phase 4 acceptance: v1 all-pass
├── smoke_v2.py                 # Phase 4 acceptance: v2 healing
└── integration_test.py         # Interactive v1→v2 healing demonstration
```
