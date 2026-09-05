"""Assembles per-page raw extractions into the canonical ApplicationModel:
pages, elements, forms, navigation links, and inferred business-intent
workflows.
"""
from __future__ import annotations

import uuid

from app.schemas.discovery import (
    ApplicationMeta,
    ApplicationModel,
    ElementModel,
    FormFieldModel,
    FormModel,
    NavigationLinkModel,
    PageModel,
    WorkflowModel,
)
from app.services.discovery.element_extractor import to_element_model

# Keyword heuristics used to infer a business-intent workflow name from
# the elements present on a page. This is deliberately simple and
# deterministic; the AI layer refines/extends workflow understanding
# during test planning, but discovery itself must not depend on the LLM.
_WORKFLOW_KEYWORDS: dict[str, list[str]] = {
    "USER_LOGIN": ["login", "sign in", "signin", "log in"],
    "USER_REGISTRATION": ["register", "sign up", "signup", "create account"],
    "PRODUCT_PURCHASE": ["add to cart", "checkout", "buy now", "purchase"],
    "PRODUCT_SEARCH": ["search"],
    "CONTACT": ["contact", "message us", "send message"],
    "PASSWORD_RESET": ["forgot password", "reset password"],
}


def _infer_workflows(page_url: str, elements: list[ElementModel]) -> list[WorkflowModel]:
    workflows: list[WorkflowModel] = []
    text_blobs: list[str] = []
    for e in elements:
        for v in (e.text, e.aria_label, e.placeholder, e.name):
            if v:
                text_blobs.append(v.lower())
    combined = " ".join(text_blobs)

    for intent, keywords in _WORKFLOW_KEYWORDS.items():
        if any(kw in combined for kw in keywords):
            involved = [
                e.id
                for e in elements
                if e.text and any(kw in e.text.lower() for kw in keywords)
            ]
            workflows.append(
                WorkflowModel(
                    id=f"wf_{uuid.uuid4().hex[:8]}",
                    name=intent.replace("_", " ").title(),
                    business_intent=intent,
                    entry_url=page_url,
                    involved_element_ids=involved,
                )
            )
    return workflows


def build_page_model(
    page_url: str,
    page_title: str,
    raw_elements: list[dict],
) -> tuple[PageModel, list[ElementModel], list[FormModel], list[NavigationLinkModel], list[WorkflowModel]]:
    elements: list[ElementModel] = []
    forms: list[FormModel] = []
    navigation: list[NavigationLinkModel] = []

    form_field_buffer: list[ElementModel] = []

    for raw in raw_elements:
        if raw.get("is_form"):
            continue
        element_id = f"el_{uuid.uuid4().hex[:10]}"
        element = to_element_model(raw, page_url, element_id)
        elements.append(element)

        if element.tag == "a" and element.href:
            navigation.append(
                NavigationLinkModel(
                    id=f"nav_{uuid.uuid4().hex[:8]}",
                    text=element.text or element.aria_label or element.href,
                    href=element.href,
                    page_url=page_url,
                )
            )
        if element.tag in ("input", "select", "textarea"):
            form_field_buffer.append(element)

    if form_field_buffer:
        submit_candidate = next(
            (
                e
                for e in elements
                if e.tag == "button"
                and e.text
                and any(k in e.text.lower() for k in ("submit", "login", "sign", "search", "send", "add", "checkout"))
            ),
            None,
        )
        forms.append(
            FormModel(
                id=f"form_{uuid.uuid4().hex[:8]}",
                name=page_title,
                page_url=page_url,
                fields=[
                    FormFieldModel(
                        element_id=f.id,
                        label=f.aria_label or f.placeholder or f.name,
                        input_type=f.input_type or f.tag,
                        required=False,
                    )
                    for f in form_field_buffer
                ],
                submit_element_id=submit_candidate.id if submit_candidate else None,
            )
        )

    workflows = _infer_workflows(page_url, elements)
    page = PageModel(url=page_url, title=page_title, element_ids=[e.id for e in elements])
    return page, elements, forms, navigation, workflows


def merge_into_application_model(
    root_url: str,
    root_title: str,
    page_results: list[tuple[PageModel, list[ElementModel], list[FormModel], list[NavigationLinkModel], list[WorkflowModel]]],
) -> ApplicationModel:
    model = ApplicationModel(application=ApplicationMeta(url=root_url, title=root_title))
    for page, elements, forms, navigation, workflows in page_results:
        model.pages.append(page)
        model.elements.extend(elements)
        model.forms.extend(forms)
        model.navigation.extend(navigation)
        model.workflows.extend(workflows)
    return model
