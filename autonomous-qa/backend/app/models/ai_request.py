from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base
from app.models.mixins import TimestampMixin, UUIDPKMixin


class AIRequest(UUIDPKMixin, TimestampMixin, Base):
    """Every call made to an LLMProvider, for cost control and audit."""

    __tablename__ = "ai_requests"

    test_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("test_runs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    operation: Mapped[str] = mapped_column(String(50), nullable=False)  # generate_test_plan|analyze_failure|suggest_healing
    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)

    prompt_summary: Mapped[str] = mapped_column(Text, nullable=False)  # redacted/truncated
    raw_response: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    succeeded: Mapped[bool] = mapped_column(default=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
