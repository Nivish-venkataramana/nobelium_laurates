"""Pydantic schemas for the canonical ApplicationModel.

This is the compact, semantic representation produced by the discovery
engine. It is what gets sent to the LLM (never the raw DOM) and what
change intelligence diffs between snapshots.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, HttpUrl


class LocatorStrategy(BaseModel):
    strategy: Literal[
        "testid", "role", "label", "name", "placeholder", "id", "text", "css", "xpath"
    ]
    value: str | None = None
    role: str | None = None
    name: str | None = None


class Locator(BaseModel):
    primary: LocatorStrategy
    fallbacks: list[LocatorStrategy] = Field(default_factory=list)


class ElementModel(BaseModel):
    id: str
    tag: str
    role: str | None = None
    text: str | None = None
    aria_label: str | None = None
    test_id: str | None = None
    name: str | None = None
    placeholder: str | None = None
    element_id_attr: str | None = Field(default=None, description="HTML id attribute")
    href: str | None = None
    input_type: str | None = None
    visible: bool = True
    enabled: bool = True
    page_url: str
    locators: Locator


class FormFieldModel(BaseModel):
    element_id: str
    label: str | None = None
    input_type: str
    required: bool = False


class FormModel(BaseModel):
    id: str
    name: str | None = None
    page_url: str
    fields: list[FormFieldModel] = Field(default_factory=list)
    submit_element_id: str | None = None


class NavigationLinkModel(BaseModel):
    id: str
    text: str
    href: str
    page_url: str


class PageModel(BaseModel):
    url: str
    title: str
    element_ids: list[str] = Field(default_factory=list)


class WorkflowModel(BaseModel):
    """A business-intent workflow inferred from forms/navigation structure."""

    id: str
    name: str
    business_intent: str
    entry_url: str
    involved_element_ids: list[str] = Field(default_factory=list)


class ApplicationMeta(BaseModel):
    url: str
    title: str


class ApplicationModel(BaseModel):
    """The canonical semantic model of a discovered application."""

    application: ApplicationMeta
    pages: list[PageModel] = Field(default_factory=list)
    elements: list[ElementModel] = Field(default_factory=list)
    forms: list[FormModel] = Field(default_factory=list)
    navigation: list[NavigationLinkModel] = Field(default_factory=list)
    workflows: list[WorkflowModel] = Field(default_factory=list)


class DiscoveryRequest(BaseModel):
    application_id: str
    url: HttpUrl
    max_pages: int = Field(default=5, ge=1, le=25)


class DiscoveryResponse(BaseModel):
    snapshot_id: str
    application_model: ApplicationModel
    element_count: int
    page_count: int
