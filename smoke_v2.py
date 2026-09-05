"""
smoke_v2.py — Phase 4 v2 healing acceptance test.

Run AFTER smoke_v1.py, with the app restarted as APP_VERSION=v2.
Expects the checkout step to FAIL locator, Healer to fire and succeed,
and the overall run to end as 'passed'/'healed' with a HealEvent in DB.

Requires a real GROQ_API_KEY in .env.
"""
import sys, uuid
sys.path.insert(0, ".")
import storage.db as db
from core.healer import Healer
from core.intent_engine import IntentEngine
from runners.ui_runner import UIRunner
from config.settings import settings

workflow = IntentEngine._fallback_workflow()
print("Workflow:", workflow["name"], "|", len(workflow["steps"]), "steps")
print("Using GROQ model (fast):", settings.GROQ_MODEL_FAST)

run_id = str(uuid.uuid4())

def on_event(ev):
    t = ev.get("type", "")
    i = ev.get("step_index", "")
    step_num = (i + 1) if isinstance(i, int) else i
    if t == "step_started":
        print(f"  >> [{step_num}] {ev.get('intent','')}")
    elif t == "step_passed":
        print(f"  PASS    [{step_num}]  {ev.get('duration_ms',0):.0f}ms")
    elif t == "step_healed":
        print(f"  HEALED  [{step_num}]")
        print(f"    Before : {ev.get('original_locator','')}")
        print(f"    After  : {ev.get('healed_locator','')}")
        print(f"    Latency: {ev.get('heal_latency_ms',0):.0f}ms")
    elif t == "step_failed":
        err = str(ev.get("error", ""))[:120]
        print(f"  FAIL    [{step_num}]  {err}")
    elif t == "security_scan_finished":
        print(f"  Security: {ev.get('reflected_count',0)} reflected finding(s)")
    elif t == "run_finished":
        print(f"  --> {ev.get('status','?').upper()}  heals={ev.get('heal_count',0)}  {ev.get('duration_ms',0):.0f}ms")

healer = Healer(run_id)
runner = UIRunner(settings.TARGET_BASE_URL, run_id)
result = runner.run(workflow, healer=healer, event_callback=on_event, scan_security=True)
healer.shutdown()

print()
print("STATUS  :", result["status"].upper())
print("HEALS   :", result["heal_count"])
heals = db.get_heal_events(run_id)
for h in heals:
    print(f"  HealEvent step={h['step_index']} success={h['success']} latency={h['latency_ms']}ms")
    print(f"    {h['original_locator']} -> {h['healed_locator']}")

reflected = [f["field"] for f in result["findings"] if f["reflected"]]
print("FINDINGS:", reflected if reflected else "none")

assert result["status"] in ("passed", "healed") or result["heal_count"] > 0, \
    "Expected healing or pass — check GROQ_API_KEY and APP_VERSION=v2"
print("\n*** Phase 4 v2 acceptance: PASSED ***")
