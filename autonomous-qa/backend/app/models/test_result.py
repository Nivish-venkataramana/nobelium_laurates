from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.mixins import TimestampMixin, UUIDPKMixin


class TestResult(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "test_results"

    test_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("test_runs.id", ondelete="CASCADE"), index=True
    )
    test_case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("test_cases.id", ondelete="CASCADE"), index=True
    )

    # PASSED | FAILED | HEALED | HEALING_FAILED | REVIEW_REQUIRED | SKIPPED | ERROR
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    engine: Mapped[str] = mapped_column(String(20), default="playwright")
    browser: Mapped[str] = mapped_column(String(20), default="chromium")

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(nullable=True)

    step_results: Mapped[list] = mapped_column(JSONB, default=list)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    screenshot_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    trace_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    console_logs: Mapped[list] = mapped_column(JSONB, default=list)
    network_failures: Mapped[list] = mapped_column(JSONB, default=list)

    risk_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    risk_level: Mapped[str | None] = mapped_column(String(20), nullable=True)
    ai_explanation: Mapped[str | None] = mapped_column(Text, nullable=True)

    test_run: Mapped["TestRun"] = relationship(back_populates="results")  # noqa: F821
    test_case: Mapped[TestCase] = relationship(back_populates="results")  # noqa: F821
