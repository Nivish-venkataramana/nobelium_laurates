from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.mixins import TimestampMixin, UUIDPKMixin


class ApplicationSnapshot(UUIDPKMixin, TimestampMixin, Base):
    """A point-in-time normalized model of the target application.

    The full ApplicationModel (pages, elements, forms, navigation,
    workflows) is stored as JSONB. This is the canonical semantic
    representation used by change intelligence, test planning, and
    healing — never the raw DOM.
    """

    __tablename__ = "application_snapshots"

    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), index=True
    )
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    root_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    title: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    application_model: Mapped[dict] = mapped_column(JSONB, nullable=False)
    element_count: Mapped[int] = mapped_column(Integer, default=0)
    page_count: Mapped[int] = mapped_column(Integer, default=0)

    application: Mapped[Application] = relationship(back_populates="snapshots")  # noqa: F821
