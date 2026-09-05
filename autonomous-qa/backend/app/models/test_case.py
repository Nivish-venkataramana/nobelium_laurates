from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.mixins import TimestampMixin, UUIDPKMixin


class TestCase(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "test_cases"

    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), index=True
    )
    external_code: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g. TC001
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    business_intent: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)  # SMOKE/FUNCTIONAL/...
    priority: Mapped[str] = mapped_column(String(20), nullable=False)  # LOW/MEDIUM/HIGH
    risk: Mapped[str] = mapped_column(String(20), nullable=False)
    expected_outcome: Mapped[str] = mapped_column(Text, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    assertions: Mapped[list] = mapped_column(JSONB, default=list)
    source: Mapped[str] = mapped_column(String(20), default="ai_generated")  # ai_generated|manual
    is_active: Mapped[bool] = mapped_column(default=True)

    steps: Mapped[list[TestStep]] = relationship(
        back_populates="test_case", cascade="all, delete-orphan", order_by="TestStep.order_index"
    )
    results: Mapped[list[TestResult]] = relationship(  # noqa: F821
        back_populates="test_case", cascade="all, delete-orphan"
    )


class TestStep(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "test_steps"

    test_case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("test_cases.id", ondelete="CASCADE"), index=True
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)  # allowlisted action
    target_element_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    locator: Mapped[dict] = mapped_column(JSONB, nullable=False)  # {primary, fallbacks}
    value: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    test_case: Mapped[TestCase] = relationship(back_populates="steps")
