"""
dashboard/app.py
------------------
Streamlit "live control room" for AegisQA — the surface judges will watch
during the demo.

Features:
  - Target URL input + "Start Autonomous Test" button
  - Live step-by-step execution stream with distinct "🔧 Locator Healed"
    indicator showing old → new locator + heal latency in ms
  - Quality Radar with four panels:
      1. UI Test Results (pass/fail per step)
      2. Security/XSS Audit table
      3. Network Latency chart
      4. Backend Log Health

All data is read through storage/db.py — no direct SQL here.

Run standalone:  streamlit run dashboard/app.py
"""

import queue
import sys
import threading
import time
import uuid
from pathlib import Path

# ── Bootstrap project root so imports work ─────────────────────────────────
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import streamlit as st

import storage.db as db
from config.settings import settings
from core.crawler import Crawler
from core.healer import Healer
from core.intent_engine import IntentEngine
from monitors.log_watcher import LogWatcher
from runners.ui_runner import UIRunner

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="AegisQA — Autonomous QA",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Session-state helpers
# ---------------------------------------------------------------------------

def _ss(key, default=None):
    """Get or initialise a Streamlit session_state value."""
    if key not in st.session_state:
        st.session_state[key] = default
    return st.session_state[key]


# ---------------------------------------------------------------------------
# Sidebar: configuration
# ---------------------------------------------------------------------------

with st.sidebar:
    st.image("https://em-content.zobj.net/source/google/387/shield_1f6e1-fe0f.png", width=64)
    st.title("AegisQA")
    st.caption("Autonomous Quality Engineering for the AI Development Era")
    st.divider()
    target_url = st.text_input(
        "Target URL",
        value=settings.TARGET_BASE_URL,
        help="The web application to test",
    )
    st.divider()
    st.markdown("**Selected Models**")
    st.caption(f"Fast: `{settings.GROQ_MODEL_FAST}`")
    st.caption(f"Reasoning: `{settings.GROQ_MODEL_REASONING}`")

# ---------------------------------------------------------------------------
# Main header
# ---------------------------------------------------------------------------

st.title("🛡️ AegisQA — Live Control Room")
st.markdown(
    "Intent-Invariant Autonomous Testing · Self-Healing Locators · "
    "Security Audit · Perf Telemetry"
)

# ---------------------------------------------------------------------------
# Run control
# ---------------------------------------------------------------------------

col_btn, col_status = st.columns([2, 5])

with col_btn:
    start_clicked = st.button("▶ Start Autonomous Test", type="primary", use_container_width=True)

# Shared state
_ss("running", False)
_ss("current_run_id", None)
_ss("event_queue", None)
_ss("events", [])
_ss("run_result", None)

# ---------------------------------------------------------------------------
# Background run thread
# ---------------------------------------------------------------------------

def _background_run(target: str, run_id: str, evt_q: queue.Queue) -> None:
    """
    Full pipeline: crawl → synthesise → execute → (healer on failure).
    Runs in a daemon thread so the Streamlit UI stays responsive.
    """
    def on_event(event: dict) -> None:
        evt_q.put(event)

    def on_anomaly(anomaly: dict) -> None:
        evt_q.put({"type": "log_anomaly", **anomaly})

    try:
        # 1. Crawl
        on_event({"type": "phase", "phase": "crawl", "message": f"Crawling {target}…"})
        crawler = Crawler()
        graph = crawler.crawl(target, max_depth=2, max_pages=10)
        on_event({"type": "phase", "phase": "crawl_done",
                  "message": f"Crawl complete — {len(graph['pages'])} page(s)"})

        # 2. Synthesise workflow
        on_event({"type": "phase", "phase": "synthesise", "message": "Synthesising workflows…"})
        engine = IntentEngine()
        workflows = engine.synthesize_workflows(graph)
        workflow = workflows[0] if workflows else engine._fallback_workflow()
        engine.generate_playwright_spec(workflow)
        on_event({"type": "phase", "phase": "synthesise_done",
                  "message": f"Workflow ready: {workflow.get('name')} ({len(workflow['steps'])} steps)"})

        # Start log watcher
        watcher = LogWatcher()
        watcher.start(settings.LOG_WATCH_PATH, run_id, on_anomaly)

        # 3. Execute
        healer = Healer(run_id)
        runner = UIRunner(target, run_id)
        result = runner.run(workflow, healer, event_callback=on_event, scan_security=True)

        watcher.stop()
        healer.shutdown()

        on_event({"type": "done", "result": result})

    except Exception as exc:
        on_event({"type": "error", "message": str(exc)})


# ---------------------------------------------------------------------------
# Trigger run
# ---------------------------------------------------------------------------

if start_clicked and not st.session_state["running"]:
    run_id = str(uuid.uuid4())
    evt_q: queue.Queue = queue.Queue()
    st.session_state["running"] = True
    st.session_state["current_run_id"] = run_id
    st.session_state["event_queue"] = evt_q
    st.session_state["events"] = []
    st.session_state["run_result"] = None

    t = threading.Thread(
        target=_background_run,
        args=(target_url, run_id, evt_q),
        daemon=True,
    )
    t.start()

# ---------------------------------------------------------------------------
# Live event stream
# ---------------------------------------------------------------------------

run_id = st.session_state["current_run_id"]
evt_q = st.session_state["event_queue"]
events: list = st.session_state["events"]

# Drain the queue into the events list on every Streamlit rerun
if evt_q is not None:
    while True:
        try:
            ev = evt_q.get_nowait()
            events.append(ev)
            if ev.get("type") in ("done", "error"):
                st.session_state["running"] = False
                if ev.get("type") == "done":
                    st.session_state["run_result"] = ev.get("result")
        except queue.Empty:
            break

# Display status badge
with col_status:
    if st.session_state["running"]:
        st.info("⏳ Test run in progress…")
    elif run_id:
        result = st.session_state.get("run_result")
        if result:
            status = result.get("status", "unknown")
            heals = result.get("heal_count", 0)
            dur = result.get("duration_ms", 0)
            if status == "passed":
                icon = "✅"
            elif status == "healed" or heals > 0:
                icon = "🔧"
            else:
                icon = "❌"
            st.success(f"{icon} Run complete — **{status.upper()}**  |  {heals} heal(s)  |  {dur:.0f} ms")
        else:
            st.info("No run yet — click 'Start Autonomous Test' to begin.")

# ---------------------------------------------------------------------------
# Step stream panel
# ---------------------------------------------------------------------------

if events:
    st.divider()
    st.subheader("📡 Live Step Stream")

    step_container = st.container()
    with step_container:
        for ev in events:
            etype = ev.get("type", "")

            if etype == "phase":
                st.markdown(f"**🔍 {ev.get('message', '')}**")

            elif etype == "step_started":
                st.markdown(
                    f"&nbsp;&nbsp;⏵ Step {ev.get('step_index', '')+1}: *{ev.get('intent', '')}*"
                )

            elif etype == "step_passed":
                dur = ev.get("duration_ms", 0)
                st.markdown(
                    f"&nbsp;&nbsp;✅ Step {ev.get('step_index', '')+1} passed `{dur:.0f} ms`"
                )

            elif etype == "step_healed":
                orig = ev.get("original_locator", "")
                healed = ev.get("healed_locator", "")
                latency = ev.get("heal_latency_ms", 0)
                st.warning(
                    f"🔧 **Locator Healed** — Step {ev.get('step_index', '')+1}\n\n"
                    f"**Before:** `{orig}`\n\n"
                    f"**After:** `{healed}`\n\n"
                    f"Heal latency: **{latency:.0f} ms**"
                )

            elif etype == "step_failed":
                st.error(
                    f"❌ Step {ev.get('step_index', '')+1} FAILED: {ev.get('error', '')}"
                )

            elif etype == "security_scan_started":
                st.markdown("**🔒 Security scan starting…**")

            elif etype == "security_scan_finished":
                n = ev.get("reflected_count", 0)
                st.markdown(f"**🔒 Security scan complete — {n} reflected finding(s)**")

            elif etype == "log_anomaly":
                st.error(
                    f"🚨 Log Anomaly: [{ev.get('category', '')}] {ev.get('summary', '')}"
                )

            elif etype == "run_finished":
                st.success(
                    f"🏁 Run finished — status={ev.get('status', '?')}  "
                    f"heals={ev.get('heal_count', 0)}"
                )

            elif etype == "error":
                st.error(f"💥 Error: {ev.get('message', '')}")

# ---------------------------------------------------------------------------
# Quality Radar (four panels) — shown after run
# ---------------------------------------------------------------------------

result = st.session_state.get("run_result")

if result or (run_id and not st.session_state["running"]):
    st.divider()
    st.subheader("📊 Quality Radar")
    col1, col2 = st.columns(2)
    col3, col4 = st.columns(2)

    # ── Panel 1: UI Test Results ─────────────────────────────────────────
    with col1:
        st.markdown("#### 🖥️ UI Test Results")
        if run_id:
            steps = db.get_steps(run_id)
            if steps:
                import pandas as pd

                df = pd.DataFrame(steps)[["step_index", "intent", "status", "duration_ms"]]
                df.columns = ["Step", "Intent", "Status", "Duration (ms)"]

                def _color(val):
                    if val == "passed":
                        return "background-color: #d4edda"
                    elif val == "healed":
                        return "background-color: #fff3cd"
                    elif val == "failed":
                        return "background-color: #f8d7da"
                    return ""

                styled = df.style.map(_color, subset=["Status"])
                st.dataframe(styled, use_container_width=True, hide_index=True)
            else:
                st.info("No steps recorded yet.")
        else:
            st.info("Run a test to see results.")

    # ── Panel 2: Security/XSS Audit ──────────────────────────────────────
    with col2:
        st.markdown("#### 🔒 Security / XSS Audit")
        if run_id:
            findings = db.get_findings(run_id)
            if findings:
                import pandas as pd

                df = pd.DataFrame(findings)[["field", "payload", "reflected", "severity"]]
                df.columns = ["Field", "Payload", "Reflected", "Severity"]
                df["Reflected"] = df["Reflected"].map({1: "⚠️ YES", 0: "✓ No", True: "⚠️ YES", False: "✓ No"})

                def _sev_color(val):
                    if val == "medium":
                        return "background-color: #fff3cd"
                    elif val == "high":
                        return "background-color: #f8d7da"
                    return ""

                styled = df.style.map(_sev_color, subset=["Severity"])
                st.dataframe(styled, use_container_width=True, hide_index=True)
            else:
                st.success("No XSS findings.")
        else:
            st.info("Run a test to see security findings.")

    # ── Panel 3: Network Latency chart ───────────────────────────────────
    with col3:
        st.markdown("#### 📶 Network Latency")
        if run_id:
            metrics = db.get_metrics(run_id)
            if metrics:
                import pandas as pd

                df = pd.DataFrame(metrics)[["url", "method", "status", "duration_ms", "anomaly"]]
                df.columns = ["URL", "Method", "Status", "Duration (ms)", "Anomaly"]
                df["URL"] = df["URL"].apply(lambda u: u.split("?")[0][-60:])

                st.bar_chart(
                    df.set_index("URL")[["Duration (ms)"]],
                    use_container_width=True,
                    color="#1d6fcc",
                )

                anomalies = df[df["Anomaly"] == 1]
                if not anomalies.empty:
                    st.warning(f"⚠️ {len(anomalies)} anomalous request(s) detected")
            else:
                st.info("No network metrics recorded yet.")
        else:
            st.info("Run a test to see latency data.")

    # ── Panel 4: Backend Log Health ──────────────────────────────────────
    with col4:
        st.markdown("#### 🪵 Backend Log Health")
        anomalies = db.get_log_anomalies(run_id=run_id, limit=20)
        if anomalies:
            for a in anomalies:
                st.error(
                    f"**[{a['category']}]** {a['summary']}\n\n"
                    f"*{a['timestamp']}*"
                )
        else:
            st.success("✅ No log anomalies detected — backend is healthy.")

# ---------------------------------------------------------------------------
# Auto-refresh while running
# ---------------------------------------------------------------------------
if st.session_state["running"]:
    time.sleep(0.8)
    st.rerun()

# ---------------------------------------------------------------------------
# Historical runs sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.divider()
    st.markdown("**Recent Runs**")
    recent = db.get_runs(limit=10)
    for r in recent:
        badge = "✅" if r["status"] == "passed" else "🔧" if r["status"] in ("healed",) else "❌"
        st.caption(
            f"{badge} `{r['run_id'][:8]}…` {r['status']} — "
            f"{r['started_at'][:16]}"
        )
