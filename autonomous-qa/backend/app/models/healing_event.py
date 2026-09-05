from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.mixins import TimestampMixin, UUIDPKMixin


class HealingEvent(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "healing_events"

    test_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("test_runs.id", ondelete="CASCADE"), index=True
    )
    test_case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("test_cases.id", ondelete="CASCADE"), index=True
    )
    test_step_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("test_steps.id", ondelete="SET NULL"), nullable=True
    )

    original_locator: Mapped[dict] = mapped_column(JSONB, nullable=False)
    replacement_locator: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    candidates_considered: Mapped[list] = mapped_column(JSONB, default=list)

    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    method: Mapped[str] = mapped_column(String(30), nullable=False)  # deterministic | ai_assisted
    reason: Mapped[str] = mapped_column(Text, nullable=False)

    # HEALED | HEALING_FAILED | REVIEW_REQUIRED
    outcome: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    verification_result: Mapped[str | None] = mapped_column(String(30), nullable=True)
    healed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    test_run: Mapped["TestRun"] = relationship(back_populates="healing_events")  # noqa: F821
