from __future__ import annotations

import uuid

from sqlalchemy import String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base
from app.models.mixins import TimestampMixin, UUIDPKMixin


class AuditLog(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "audit_logs"

    actor: Mapped[str] = mapped_column(String(255), default="system")
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
