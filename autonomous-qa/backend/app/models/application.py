from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.mixins import TimestampMixin, UUIDPKMixin


class Application(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "applications"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    base_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    browser_engine: Mapped[str] = mapped_column(String(50), default="playwright")

    project: Mapped[Project] = relationship(back_populates="applications")  # noqa: F821
    snapshots: Mapped[list[ApplicationSnapshot]] = relationship(  # noqa: F821
        back_populates="application", cascade="all, delete-orphan", order_by="ApplicationSnapshot.created_at"
    )
