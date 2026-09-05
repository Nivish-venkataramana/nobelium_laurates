"""
monitors/log_watcher.py
--------------------------
Non-blocking tailer for the target app's log file.

Classifies error blocks and stack traces via Groq inference so backend health
can be shown alongside UI/security/perf results on the dashboard.

Public API:
    watcher = LogWatcher()
    watcher.start(path, run_id, on_anomaly)   # returns immediately (background thread)
    watcher.stop()

LogAnomaly shape is documented in docs/SCHEMAS.md.
"""

import logging
import queue
import re
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from groq import Groq

import storage.db as db
from config.settings import settings

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Groq prompt
# ---------------------------------------------------------------------------

_CLASSIFY_SYSTEM = """You are a site-reliability engineer reviewing application logs.
Given a block of log text, determine if it represents an error, exception, or anomaly.

Respond ONLY with a JSON object (no markdown) with these fields:
{
  "is_anomaly": true | false,
  "category":   "unhandled_exception" | "http_error" | "timeout" | "db_error" | "other" | "none",
  "summary":    "<one-sentence human summary>"
}

Normal request log lines (access logs) are NOT anomalies.
Stack traces, ERROR-level lines, and unhandled exceptions ARE anomalies."""

_CLASSIFY_USER = "Log block:\n{block}"

# Regex patterns that signal the start of an anomaly block worth buffering
_ANOMALY_START_RE = re.compile(
    r"(ERROR|CRITICAL|EXCEPTION|Traceback|Error:|Exception:|raise )",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# LogWatcher
# ---------------------------------------------------------------------------

class LogWatcher:
    """
    Daemon thread that tails *path*, buffers multi-line stack traces, and
    classifies anomaly blocks via Groq.

    Parameters
    ----------
    None — call start() to begin watching.
    """

    def __init__(self) -> None:
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._groq = Groq(api_key=settings.GROQ_API_KEY)
        self._classify_queue: queue.Queue[str] = queue.Queue()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def start(
        self,
        path: str,
        run_id: str | None,
        on_anomaly: Callable[[dict], None],
    ) -> None:
        """
        Begin watching *path* in a background daemon thread.

        Safe to call before *path* exists — will poll until it appears.

        Parameters
        ----------
        path:        Path to the log file to tail.
        run_id:      Current test run ID (for DB persistence). May be None.
        on_anomaly:  Callback invoked with a LogAnomaly dict for each classified anomaly.
        """
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._watch_loop,
            args=(path, run_id, on_anomaly),
            daemon=True,
            name="log-watcher",
        )
        self._thread.start()
        log.info("LogWatcher started → %s", path)

    def stop(self) -> None:
        """Signal the watcher to stop. Does not block."""
        self._stop_event.set()
        log.debug("LogWatcher stop requested")

    # ------------------------------------------------------------------
    # Tail loop
    # ------------------------------------------------------------------

    def _watch_loop(
        self,
        path: str,
        run_id: str | None,
        on_anomaly: Callable[[dict], None],
    ) -> None:
        log_path = Path(path)

        # Wait until file exists
        while not self._stop_event.is_set() and not log_path.exists():
            log.debug("LogWatcher: waiting for %s to appear…", path)
            time.sleep(1.0)

        buffer: list[str] = []
        in_block = False
        last_pos = 0

        # Seek to end on first open (only tail new lines)
        try:
            last_pos = log_path.stat().st_size
        except Exception:
            last_pos = 0

        while not self._stop_event.is_set():
            try:
                current_size = log_path.stat().st_size
            except FileNotFoundError:
                # File rotated / deleted — reset
                last_pos = 0
                time.sleep(0.5)
                continue

            if current_size < last_pos:
                # Truncation / rotation detected
                log.debug("LogWatcher: file truncated — resetting position")
                last_pos = 0

            if current_size > last_pos:
                try:
                    with open(log_path, "r", encoding="utf-8", errors="replace") as fh:
                        fh.seek(last_pos)
                        new_text = fh.read()
                    last_pos = current_size
                except Exception as exc:
                    log.debug("LogWatcher read error: %s", exc)
                    time.sleep(0.5)
                    continue

                for line in new_text.splitlines(keepends=True):
                    stripped = line.rstrip()
                    if not stripped:
                        # Blank line = potential end of a multi-line block
                        if buffer and in_block:
                            self._flush_block("".join(buffer), run_id, on_anomaly)
                            buffer = []
                            in_block = False
                        continue

                    if _ANOMALY_START_RE.search(stripped):
                        in_block = True
                        buffer.append(stripped + "\n")
                    elif in_block:
                        buffer.append(stripped + "\n")
                    # else: normal access log line — ignore

            else:
                time.sleep(0.2)

        # Flush remaining buffer on stop
        if buffer and in_block:
            self._flush_block("".join(buffer), run_id, on_anomaly)

    # ------------------------------------------------------------------
    # Block classification via Groq
    # ------------------------------------------------------------------

    def _flush_block(
        self,
        block: str,
        run_id: str | None,
        on_anomaly: Callable[[dict], None],
    ) -> None:
        """Classify a buffered log block and fire on_anomaly if warranted."""
        log.debug("LogWatcher: classifying block (%d chars)", len(block))
        result = self._classify(block)

        if not result or not result.get("is_anomaly"):
            return

        timestamp = datetime.now(timezone.utc).isoformat()
        anomaly: dict = {
            "category": result.get("category", "other"),
            "summary": result.get("summary", ""),
            "raw_block": block,
            "timestamp": timestamp,
        }

        # Persist
        try:
            db.insert_log_anomaly(
                run_id=run_id,
                category=anomaly["category"],
                summary=anomaly["summary"],
                raw_block=block,
                timestamp=timestamp,
            )
        except Exception as exc:
            log.error("LogWatcher: DB persist error: %s", exc)

        log.info(
            "LogWatcher: anomaly detected — category=%s  summary=%s",
            anomaly["category"], anomaly["summary"],
        )

        try:
            on_anomaly(anomaly)
        except Exception as exc:
            log.debug("on_anomaly callback raised: %s", exc)

    def _classify(self, block: str) -> dict | None:
        """Ask Groq (GROQ_MODEL_FAST) to classify the log block."""
        try:
            response = self._groq.chat.completions.create(
                model=settings.GROQ_MODEL_FAST,
                messages=[
                    {"role": "system", "content": _CLASSIFY_SYSTEM},
                    {"role": "user", "content": _CLASSIFY_USER.format(block=block[:3000])},
                ],
                temperature=0.0,
                max_tokens=256,
                response_format={"type": "json_object"},
            )
            import json
            raw = response.choices[0].message.content or "{}"
            return json.loads(raw)
        except Exception as exc:
            log.error("LogWatcher: Groq classify failed: %s", exc)
            # Fallback heuristic: if block contains "ERROR" it's an anomaly
            if "ERROR" in block.upper() or "TRACEBACK" in block.upper():
                return {
                    "is_anomaly": True,
                    "category": "unhandled_exception",
                    "summary": block.splitlines()[0][:120],
                }
            return None
