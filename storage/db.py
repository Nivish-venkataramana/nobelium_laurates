"""
storage/db.py
--------------
Single SQLite helper for AegisQA. Every module that needs persistence calls
functions from here — no ad-hoc sqlite3.connect() calls elsewhere.

Tables (schema per docs/SCHEMAS.md):
    runs(run_id, target_url, started_at, finished_at, status)
    steps(run_id, step_index, intent, status, duration_ms)
    heal_events(run_id, step_index, original_locator, healed_locator, latency_ms, success)
    findings(run_id, field, payload, reflected, severity)
    request_metrics(run_id, url, method, status, duration_ms, anomaly)
    log_anomalies(run_id, category, summary, timestamp)
"""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config.settings import settings

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _db_path() -> str:
    path = Path(settings.SQLITE_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    return str(path)


def _connect() -> sqlite3.Connection:
    """Open a connection with row_factory so callers get dict-like rows."""
    conn = sqlite3.connect(_db_path(), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")   # allow concurrent readers
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


# ---------------------------------------------------------------------------
# Schema bootstrap
# ---------------------------------------------------------------------------

_DDL = """
CREATE TABLE IF NOT EXISTS runs (
    run_id       TEXT PRIMARY KEY,
    target_url   TEXT NOT NULL,
    started_at   TEXT NOT NULL,
    finished_at  TEXT,
    status       TEXT NOT NULL DEFAULT 'running'
);

CREATE TABLE IF NOT EXISTS steps (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id       TEXT NOT NULL REFERENCES runs(run_id),
    step_index   INTEGER NOT NULL,
    intent       TEXT NOT NULL,
    status       TEXT NOT NULL,
    duration_ms  REAL
);

CREATE TABLE IF NOT EXISTS heal_events (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id            TEXT NOT NULL REFERENCES runs(run_id),
    step_index        INTEGER NOT NULL,
    original_locator  TEXT,
    healed_locator    TEXT,
    latency_ms        REAL,
    success           INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS findings (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id     TEXT NOT NULL REFERENCES runs(run_id),
    field      TEXT NOT NULL,
    payload    TEXT NOT NULL,
    reflected  INTEGER NOT NULL DEFAULT 0,
    severity   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS request_metrics (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id      TEXT NOT NULL REFERENCES runs(run_id),
    url         TEXT NOT NULL,
    method      TEXT NOT NULL,
    status      INTEGER,
    duration_ms REAL,
    anomaly     INTEGER NOT NULL DEFAULT 0,
    step_index  INTEGER
);

CREATE TABLE IF NOT EXISTS log_anomalies (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id    TEXT,
    category  TEXT NOT NULL,
    summary   TEXT NOT NULL,
    raw_block TEXT,
    timestamp TEXT NOT NULL
);
"""


def init_db() -> None:
    """Create all tables if they don't exist. Safe to call on every startup."""
    with _connect() as conn:
        conn.executescript(_DDL)


# ---------------------------------------------------------------------------
# Run management
# ---------------------------------------------------------------------------

def create_run(run_id: str, target_url: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        conn.execute(
            "INSERT INTO runs (run_id, target_url, started_at, status) VALUES (?,?,?,?)",
            (run_id, target_url, now, "running"),
        )


def update_run(run_id: str, status: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        conn.execute(
            "UPDATE runs SET status=?, finished_at=? WHERE run_id=?",
            (status, now, run_id),
        )


def get_runs(limit: int = 50) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM runs ORDER BY started_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Steps
# ---------------------------------------------------------------------------

def insert_step(run_id: str, step_index: int, intent: str, status: str, duration_ms: float | None) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT INTO steps (run_id, step_index, intent, status, duration_ms) VALUES (?,?,?,?,?)",
            (run_id, step_index, intent, status, duration_ms),
        )


def get_steps(run_id: str) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM steps WHERE run_id=? ORDER BY step_index", (run_id,)
        ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Heal events
# ---------------------------------------------------------------------------

def insert_heal_event(
    run_id: str,
    step_index: int,
    original_locator: str | None,
    healed_locator: str | None,
    latency_ms: float,
    success: bool,
) -> None:
    with _connect() as conn:
        conn.execute(
            """INSERT INTO heal_events
               (run_id, step_index, original_locator, healed_locator, latency_ms, success)
               VALUES (?,?,?,?,?,?)""",
            (run_id, step_index, original_locator, healed_locator, latency_ms, int(success)),
        )


def get_heal_events(run_id: str) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM heal_events WHERE run_id=? ORDER BY step_index", (run_id,)
        ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Security findings
# ---------------------------------------------------------------------------

def insert_finding(
    run_id: str,
    field: str,
    payload: str,
    reflected: bool,
    severity: str,
) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT INTO findings (run_id, field, payload, reflected, severity) VALUES (?,?,?,?,?)",
            (run_id, field, payload, int(reflected), severity),
        )


def get_findings(run_id: str) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM findings WHERE run_id=?", (run_id,)
        ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Request metrics
# ---------------------------------------------------------------------------

def insert_request_metric(
    run_id: str,
    url: str,
    method: str,
    status: int | None,
    duration_ms: float,
    anomaly: bool,
    step_index: int | None = None,
) -> None:
    with _connect() as conn:
        conn.execute(
            """INSERT INTO request_metrics
               (run_id, url, method, status, duration_ms, anomaly, step_index)
               VALUES (?,?,?,?,?,?,?)""",
            (run_id, url, method, status, duration_ms, int(anomaly), step_index),
        )


def get_metrics(run_id: str) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM request_metrics WHERE run_id=? ORDER BY id", (run_id,)
        ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Log anomalies
# ---------------------------------------------------------------------------

def insert_log_anomaly(
    run_id: str | None,
    category: str,
    summary: str,
    raw_block: str,
    timestamp: str | None = None,
) -> None:
    ts = timestamp or datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        conn.execute(
            """INSERT INTO log_anomalies (run_id, category, summary, raw_block, timestamp)
               VALUES (?,?,?,?,?)""",
            (run_id, category, summary, raw_block, ts),
        )


def get_log_anomalies(run_id: str | None = None, limit: int = 100) -> list[dict]:
    with _connect() as conn:
        if run_id:
            rows = conn.execute(
                "SELECT * FROM log_anomalies WHERE run_id=? ORDER BY timestamp DESC LIMIT ?",
                (run_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM log_anomalies ORDER BY timestamp DESC LIMIT ?", (limit,)
            ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Convenience: initialise on first import (idempotent)
# ---------------------------------------------------------------------------
init_db()
