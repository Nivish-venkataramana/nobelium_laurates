# AegisQA — Shared Data Schemas

These are the contracts between modules. Keep them stable; if a phase needs
to change one, update this file in the same commit.

## CrawlGraph (produced by `core/crawler.py`)

```json
{
  "base_url": "http://localhost:5000",
  "pages": [
    {
      "url": "/checkout",
      "title": "Checkout",
      "a11y_snapshot": { "...": "raw output of page.accessibility.snapshot()" },
      "interactive_elements": [
        {
          "role": "button",
          "accessible_name": "Checkout",
          "selector_hint": "#checkout",
          "bounding_box": {"x": 0, "y": 0, "width": 0, "height": 0}
        }
      ],
      "forms": [
        {
          "form_id": "checkout-form",
          "fields": [
            {"role": "textbox", "accessible_name": "Promo code", "input_type": "text"}
          ]
        }
      ],
      "links": ["/cart", "/"]
    }
  ]
}
```

## Workflow (produced by `core/intent_engine.py`)

```json
{
  "name": "Search and Add to Cart",
  "steps": [
    {
      "intent": "search for a product",
      "role": "textbox",
      "accessible_name": "Search",
      "action_type": "fill",
      "value": "blue shirt",
      "expected_outcome": "search results list is visible"
    },
    {
      "intent": "add first result to cart",
      "role": "button",
      "accessible_name": "Add to cart",
      "action_type": "click",
      "expected_outcome": "cart item count increases by 1"
    }
  ]
}
```

## HealEvent (produced by `core/healer.py`, persisted to SQLite)

```json
{
  "run_id": "uuid",
  "step_index": 2,
  "original_intent": {"role": "button", "accessible_name": "Checkout"},
  "original_locator": "#checkout",
  "healed_locator": "role=button[name='Continue']",
  "latency_ms": 214,
  "success": true,
  "timestamp": "2026-09-05T10:00:00Z"
}
```

## Finding (produced by `runners/security_scanner.py`)

```json
{
  "field": "promo_code",
  "payload": "\"><script>console.log(1)</script>",
  "reflected": true,
  "severity": "medium",
  "evidence": "payload found unescaped in response HTML"
}
```

## RequestMetric (produced by `runners/perf_monitor.py`)

```json
{
  "url": "/api/cart",
  "method": "POST",
  "status": 200,
  "duration_ms": 412,
  "anomaly": false,
  "step_index": 2
}
```

## LogAnomaly (produced by `monitors/log_watcher.py`)

```json
{
  "category": "unhandled_exception",
  "summary": "NullPointerException in checkout handler",
  "raw_block": "...",
  "timestamp": "2026-09-05T10:00:03Z"
}
```

## SQLite tables (`storage/test_runs.db`)

- `runs(run_id, target_url, started_at, finished_at, status)`
- `steps(run_id, step_index, intent, status, duration_ms)`
- `heal_events(run_id, step_index, original_locator, healed_locator, latency_ms, success)`
- `findings(run_id, field, payload, reflected, severity)`
- `request_metrics(run_id, url, method, status, duration_ms, anomaly)`
- `log_anomalies(run_id, category, summary, timestamp)`

All writes should go through a single `storage/db.py` helper (to be created
in Phase 4) rather than ad-hoc `sqlite3` calls scattered across modules.
