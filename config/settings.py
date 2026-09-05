"""
config/settings.py
-------------------
Centralized, typed configuration for AegisQA. Every other module should
import `settings` from here rather than reading os.environ directly.

Load order: environment variables > .env file > defaults defined below.
Fails fast with a clear ValidationError if GROQ_API_KEY is missing.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    AegisQA configuration — sourced from .env / environment variables.

    Required:
        GROQ_API_KEY  — must be set in .env or the environment before any
                        Groq-dependent module is imported.

    All other fields have sensible defaults and can be overridden in .env.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,       # ENV_VAR or env_var both work
        extra="ignore",             # tolerate unknown vars in .env
    )

    # ── Groq inference ──────────────────────────────────────────────────
    GROQ_API_KEY: str                                   # required — no default

    # Latency-critical healer / log-watcher calls (≤300 ms target)
    GROQ_MODEL_FAST: str = "llama-3.1-8b-instant"

    # Workflow synthesis / anomaly classification (correctness over speed)
    GROQ_MODEL_REASONING: str = "llama-3.3-70b-versatile"

    # ── Healer tuning ────────────────────────────────────────────────────
    HEALER_TIMEOUT_MS: int = 300        # hard wall-clock limit per Groq call

    # ── Crawler limits ───────────────────────────────────────────────────
    CRAWLER_MAX_DEPTH: int = 3
    CRAWLER_MAX_PAGES: int = 25

    # ── Target application ───────────────────────────────────────────────
    TARGET_BASE_URL: str = "http://localhost:5000"
    SAMPLE_APP_PORT: int = 5000
    DASHBOARD_PORT: int = 8501

    # ── Persistence ──────────────────────────────────────────────────────
    SQLITE_PATH: str = "storage/test_runs.db"
    LOG_WATCH_PATH: str = "storage/app.log"

    # ── Logging ──────────────────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"

    # ── Security scanner ─────────────────────────────────────────────────
    # "standard" = OWASP boundary/XSS probes only
    # "extended" = also includes longer overflow + SQLi markers
    OWASP_PAYLOAD_SET: str = "standard"


# Module-level singleton — import this everywhere:
#   from config.settings import settings
settings = Settings()
