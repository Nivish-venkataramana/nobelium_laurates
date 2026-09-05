from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None


class ProjectOut(BaseModel):
    id: str
    name: str
    description: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
