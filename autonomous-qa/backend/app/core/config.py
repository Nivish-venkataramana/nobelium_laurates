"""Application configuration.

All runtime configuration is loaded from environment variables (see
.env.example). Nothing here is hardcoded to a specific deployment.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- App ---
    APP_NAME: str = "Autonomous Quality Engineering Platform"
    ENVIRONMENT: str = Field(default="development")  # development | production
    LOG_LEVEL: str = "INFO"
    JWT_SECRET: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60 * 24

    # --- Database ---
    DATABASE_URL: str = "postgresql+psycopg2://qa_user:qa_password@localhost:5432/autonomous_qa"
    ASYNC_DATABASE_URL: str = "postgresql+asyncpg://qa_user:qa_password@localhost:5432/autonomous_qa"

    # --- Redis / Celery ---
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # --- AI ---
    AI_PROVIDER: str = "groq"
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    AI_MAX_RETRIES: int = 2
    AI_TIMEOUT_SECONDS: int = 60

    # --- Browser automation ---
    BROWSER_HEADLESS: bool = True
    BROWSER_TIMEOUT_MS: int = 30000
    BROWSER_ENGINE_DEFAULT: str = "playwright"  # playwright | selenium
    MAX_CONCURRENT_BROWSER_CONTEXTS: int = 3

    # --- Test generation / execution limits ---
    MAX_TESTS_PER_RUN: int = 25
    RUN_TIMEOUT_SECONDS: int = 900

    # --- Self-healing ---
    HEALING_ENABLED: bool = True
    HEALING_CONFIDENCE_THRESHOLD: float = 0.85
    HEALING_LLM_FALLBACK_ENABLED: bool = True

    # --- Security / SSRF protection ---
    ALLOWED_DOMAINS: str = ""  # comma-separated allowlist; empty = allow any public domain
    ALLOW_PRIVATE_NETWORK_TARGETS: bool = False  # set True only in local dev with demo-app
    MAX_REQUEST_BODY_BYTES: int = 2_000_000
    RATE_LIMIT_PER_MINUTE: int = 60

    # --- Data retention (days); 0 = keep forever ---
    RETENTION_SCREENSHOTS_DAYS: int = 30
    RETENTION_TRACES_DAYS: int = 14
    RETENTION_AI_REQUESTS_DAYS: int = 90
    RETENTION_SNAPSHOTS_DAYS: int = 180

    @field_validator("ALLOWED_DOMAINS")
    @classmethod
    def _normalize_domains(cls, v: str) -> str:
        return v.strip()

    @property
    def allowed_domains_list(self) -> list[str]:
        return [d.strip().lower() for d in self.ALLOWED_DOMAINS.split(",") if d.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
