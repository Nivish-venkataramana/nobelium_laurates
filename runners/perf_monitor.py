"""
runners/perf_monitor.py
--------------------------
Passive network telemetry collector.

Hooks Playwright's request/response events to measure per-request latency,
correlates requests with the current step index, and flags anomalies
(>800 ms or 4xx/5xx responses).

Public API:
    monitor = PerfMonitor()
    monitor.attach(page)                  # call once per page object
    monitor.set_step(step_index)          # call before each step
    metrics = monitor.get_metrics()       # -> list[RequestMetric]

RequestMetric shape is documented in docs/SCHEMAS.md.
"""

import logging
import time
from threading import Lock
from typing import Any

log = logging.getLogger(__name__)

# Threshold for flagging a request as a latency anomaly (ms)
_LATENCY_THRESHOLD_MS = 800


class PerfMonitor:
    """
    Passive network telemetry collector attached to a Playwright Page.

    Thread-safe — Playwright fires events on its own internal thread.
    """

    def __init__(self) -> None:
        self._metrics: list[dict] = []
        self._pending: dict[str, float] = {}   # request_id → start_time (monotonic)
        self._current_step: int = 0
        self._lock = Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def attach(self, page) -> None:
        """
        Hook Playwright page.on("request") and page.on("response").

        Must be called once per Page object before navigation begins.
        """
        page.on("request", self._on_request)
        page.on("response", self._on_response)
        page.on("requestfailed", self._on_request_failed)
        log.debug("PerfMonitor attached to page")

    def set_step(self, step_index: int) -> None:
        """Annotate subsequent requests with *step_index*."""
        with self._lock:
            self._current_step = step_index

    def get_metrics(self) -> list[dict]:
        """Return all collected RequestMetric dicts (copies)."""
        with self._lock:
            return list(self._metrics)

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_request(self, request) -> None:
        with self._lock:
            self._pending[request.url] = time.monotonic()

    def _on_response(self, response) -> None:
        url = response.url
        with self._lock:
            start = self._pending.pop(url, None)
            step_index = self._current_step

        if start is None:
            return   # no matching request (e.g. cached)

        duration_ms = (time.monotonic() - start) * 1000
        status = response.status
        anomaly = duration_ms > _LATENCY_THRESHOLD_MS or status >= 400

        metric = {
            "url": url,
            "method": response.request.method,
            "status": status,
            "duration_ms": round(duration_ms, 1),
            "anomaly": anomaly,
            "step_index": step_index,
        }

        with self._lock:
            self._metrics.append(metric)

        if anomaly:
            log.debug(
                "PerfMonitor anomaly: %s %s -> %d  %.0f ms",
                response.request.method, url, status, duration_ms,
            )

    def _on_request_failed(self, request) -> None:
        url = request.url
        with self._lock:
            start = self._pending.pop(url, None)
            step_index = self._current_step

        duration_ms = (time.monotonic() - (start or time.monotonic())) * 1000

        metric = {
            "url": url,
            "method": request.method,
            "status": None,
            "duration_ms": round(duration_ms, 1),
            "anomaly": True,
            "step_index": step_index,
        }
        with self._lock:
            self._metrics.append(metric)

        log.warning("PerfMonitor: request failed: %s %s", request.method, url)
