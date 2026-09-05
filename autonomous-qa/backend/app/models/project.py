from __future__ import annotations

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.mixins import TimestampMixin, UUIDPKMixin


class Project(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "projects"

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    applications: Mapped[list[Application]] = relationship(  # noqa: F821
        back_populates="project", cascade="all, delete-orphan"
    )
