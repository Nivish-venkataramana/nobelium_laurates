from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class ApplicationCreate(BaseModel):
    project_id: str
    name: str = Field(min_length=1, max_length=255)
    base_url: HttpUrl
    browser_engine: str = Field(default="playwright", pattern="^(playwright|selenium)$")


class ApplicationOut(BaseModel):
    id: str
    project_id: str
    name: str
    base_url: str
    browser_engine: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
