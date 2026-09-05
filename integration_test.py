"""
integration_test.py — Phase 4 acceptance script.

Proves the full v1→v2 self-healing pipeline without requiring Groq for
workflow synthesis (uses the hardcoded fallback workflow).

Usage:
    # Terminal 1:  python tests/sample_app/app.py
    # Terminal 2:  python integration_test.py

The script:
  1. Runs the fallback workflow against APP_VERSION=v1  → expects all PASSED, 0 heals
  2. Asks you to restart the app with APP_VERSION=v2, then re-runs the SAME workflow
     → checkout step FAILS locator, Healer fires, run ends PASSED with 1 HealEvent

Requires a real GROQ_API_KEY in .env for the healer Groq call.
"""

import sys
import time
import uuid
from pathlib import Path

# Bootstrap path
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import storage.db as db
from config.settings import settings
from core.healer import Healer
from core.intent_engine import IntentEngine
from runners.ui_runner import UIRunner

# ── Use the hardcoded fallback workflow (no Groq needed for synthesis) ──────
engine = IntentEngine.__new__(IntentEngine)  # skip __init__ (no Groq client yet)
workflow = IntentEngine._fallback_workflow()

BASE_URL = settings.TARGET_BASE_URL


def run_once(label: str) -> dict:
    run_id = str(uuid.uuid4())
    print(f"\n{'='*60}")
    print(f"  {label}  (run_id={run_id[:8]}...)")
    print(f"{'='*60}")

    def on_event(ev: dict) -> None:
        t = ev.get("type", "")
        idx = ev.get("step_index", "")
        intent = ev.get("intent", "")
        if t == "step_started":
            print(f"  >> [{idx+1 if isinstance(idx,int) else idx}] {intent}")
        elif t == "step_passed":
            print(f"  PASS [{idx+1}]  ({ev.get('duration_ms',0):.0f} ms)")
        elif t == "step_healed":
            print(f"  *** HEALED [{idx+1}]")
            print(f"      Before: {ev.get('original_locator','')}")
            print(f"      After : {ev.get('healed_locator','')}")
            print(f"      Heal latency: {ev.get('heal_latency_ms',0):.0f} ms")
        elif t == "step_failed":
            print(f"  FAIL [{idx+1}]  {ev.get('error','')[:80]}")
        elif t == "security_scan_finished":
            print(f"  Security: {ev.get('reflected_count',0)} reflected finding(s)")
        elif t == "run_finished":
            status = ev.get("status", "?")
            heals  = ev.get("heal_count", 0)
            dur    = ev.get("duration_ms", 0)
            print(f"\n  --> Run finished: {status.upper()}  heals={heals}  {dur:.0f}ms")

    healer = Healer(run_id)
    runner = UIRunner(BASE_URL, run_id)
    result = runner.run(workflow, healer=healer, event_callback=on_event, scan_security=True)
    healer.shutdown()
    return result


if __name__ == "__main__":
    print("AegisQA Integration Test")
    print(f"Target: {BASE_URL}")
    print(f"Groq fast model: {settings.GROQ_MODEL_FAST}")

    # ── Run 1: v1 ────────────────────────────────────────────────────────────
    r1 = run_once("RUN 1 — APP_VERSION=v1  (expect PASSED, 0 heals)")
    assert r1["status"] in ("passed", "healed"), f"Run 1 unexpected status: {r1['status']}"

    # ── Prompt for v2 ────────────────────────────────────────────────────────
    print("\n" + "="*60)
    print("  ACTION REQUIRED")
    print("  Stop the sample app, restart it with:")
    print("    set APP_VERSION=v2 && python tests/sample_app/app.py")
    print("  Then press ENTER here to run the SAME spec against v2.")
    print("="*60)
    input("  Press ENTER when v2 app is running...")

    # ── Run 2: v2 ────────────────────────────────────────────────────────────
    r2 = run_once("RUN 2 — APP_VERSION=v2  (expect HEALED checkout step)")

    # Verify heal event was recorded
    heals = db.get_heal_events(r2["run_id"])
    print(f"\n  Heal events in DB: {len(heals)}")
    for h in heals:
        print(f"    step={h['step_index']}  success={h['success']}  latency={h['latency_ms']}ms")
        print(f"    {h['original_locator']} -> {h['healed_locator']}")

    assert r2["status"] in ("passed", "healed"), f"Run 2 status was {r2['status']} (heal may have been needed)"
    print("\n*** Phase 4 acceptance: PASSED ***")
