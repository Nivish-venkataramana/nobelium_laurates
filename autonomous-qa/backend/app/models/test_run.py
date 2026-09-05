from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.mixins import TimestampMixin, UUIDPKMixin


class RunStatus(str, enum.Enum):
    CREATED = "CREATED"
    QUEUED = "QUEUED"
    DISCOVERING = "DISCOVERING"
    PLANNING = "PLANNING"
    GENERATING = "GENERATING"
    VALIDATING = "VALIDATING"
    EXECUTING = "EXECUTING"
    ANALYZING = "ANALYZING"
    HEALING = "HEALING"
    RETESTING = "RETESTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


ALLOWED_TRANSITIONS: dict[RunStatus, set[RunStatus]] = {
    RunStatus.CREATED: {RunStatus.QUEUED, RunStatus.CANCELLED},
    RunStatus.QUEUED: {RunStatus.DISCOVERING, RunStatus.PLANNING, RunStatus.EXECUTING, RunStatus.CANCELLED, RunStatus.FAILED},
    RunStatus.DISCOVERING: {RunStatus.PLANNING, RunStatus.EXECUTING, RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED},
    RunStatus.PLANNING: {RunStatus.GENERATING, RunStatus.EXECUTING, RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED},
    RunStatus.GENERATING: {RunStatus.VALIDATING, RunStatus.EXECUTING, RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED},
    RunStatus.VALIDATING: {RunStatus.EXECUTING, RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED},
    RunStatus.EXECUTING: {RunStatus.ANALYZING, RunStatus.HEALING, RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED},
    RunStatus.ANALYZING: {RunStatus.HEALING, RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED},
    RunStatus.HEALING: {RunStatus.RETESTING, RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED},
    RunStatus.RETESTING: {RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED},
    RunStatus.COMPLETED: set(),
    RunStatus.FAILED: set(),
    RunStatus.CANCELLED: set(),
}


class TestRun(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "test_runs"

    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[RunStatus] = mapped_column(
        Enum(RunStatus, name="run_status"), default=RunStatus.CREATED, index=True
    )
    trigger: Mapped[str] = mapped_column(String(50), default="manual")  # manual|scheduled|rerun
    run_discovery: Mapped[bool] = mapped_column(default=True)
    run_generation: Mapped[bool] = mapped_column(default=True)
    max_tests: Mapped[int] = mapped_column(Integer, default=25)
    single_test_case_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("test_cases.id", ondelete="SET NULL"), nullable=True
    )

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=900)

    tests_generated: Mapped[int] = mapped_column(Integer, default=0)
    tests_executed: Mapped[int] = mapped_column(Integer, default=0)
    tests_passed: Mapped[int] = mapped_column(Integer, default=0)
    tests_failed: Mapped[int] = mapped_column(Integer, default=0)
    tests_healed: Mapped[int] = mapped_column(Integer, default=0)
    tests_review_required: Mapped[int] = mapped_column(Integer, default=0)

    quality_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quality_score_breakdown: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    ai_explanation: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(2048), nullable=True)

    results: Mapped[list[TestResult]] = relationship(  # noqa: F821
        back_populates="test_run", cascade="all, delete-orphan"
    )
    healing_events: Mapped[list[HealingEvent]] = relationship(  # noqa: F821
        back_populates="test_run", cascade="all, delete-orphan"
    )
