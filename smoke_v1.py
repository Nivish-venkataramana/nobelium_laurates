"""Quick v1 smoke test — no Groq key needed."""
import sys, uuid
sys.path.insert(0, ".")
import storage.db as db
from core.intent_engine import IntentEngine
from runners.ui_runner import UIRunner
from config.settings import settings

workflow = IntentEngine._fallback_workflow()
print("Workflow:", workflow["name"], "|", len(workflow["steps"]), "steps")

run_id = str(uuid.uuid4())

def on_event(ev):
    t = ev.get("type", "")
    i = ev.get("step_index", "")
    step_num = (i + 1) if isinstance(i, int) else i
    if t == "step_started":
        print(f"  >> [{step_num}] {ev.get('intent','')}")
    elif t == "step_passed":
        print(f"  PASS [{step_num}]  {ev.get('duration_ms',0):.0f}ms")
    elif t == "step_healed":
        print(f"  HEALED [{step_num}] {ev.get('original_locator','')} -> {ev.get('healed_locator','')}  {ev.get('heal_latency_ms',0):.0f}ms")
    elif t == "step_failed":
        err = str(ev.get("error", ""))[:100]
        print(f"  FAIL [{step_num}]  {err}")
    elif t == "security_scan_finished":
        print(f"  Security: {ev.get('reflected_count',0)} reflected finding(s)")

runner = UIRunner(settings.TARGET_BASE_URL, run_id)
result = runner.run(workflow, healer=None, event_callback=on_event, scan_security=True)

print()
print("STATUS  :", result["status"].upper())
print("HEALS   :", result["heal_count"])
print("STEPS   :", [(s["step_index"], s["status"]) for s in result["steps"]])
reflected = [f["field"] for f in result["findings"] if f["reflected"]]
print("FINDINGS:", reflected if reflected else "none")
