"""AI test planning orchestration.

Pipeline (per the platform's non-negotiable safety rule):

    ApplicationModel -> prompt -> LLMProvider -> raw text
        -> JSON extraction -> Pydantic schema validation
        -> semantic validation (element ids must exist)
        -> safety validation (allowlisted actions/assertions only,
           already enforced by the schema)
        -> persisted TestCase/TestStep rows

The LLM never writes to the database directly and never decides
pass/fail; it only proposes a validated plan.
"""
from __future__ import annotations

from datetime import UTC, datetime

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.exceptions import InvalidTestPlanError
from app.core.logging import get_logger
from app.models.ai_request import AIRequest
from app.models.test_case import TestCase, TestStep
from app.schemas.discovery import ApplicationModel
from app.schemas.test_case import TestCasePlan, TestPlanResponse
from app.services.ai.json_extract import extract_json_object
from app.services.ai.prompts import TEST_PLANNER_SYSTEM_PROMPT, build_test_planning_task_prompt
from app.services.ai.provider import LLMProvider

logger = get_logger(__name__)


def _validate_element_references(plan: TestPlanResponse, valid_element_ids: set[str]) -> list[TestCasePlan]:
    """Semantic validation: drop/repair tests that reference element ids
    which do not actually exist in the ApplicationModel we sent."""
    valid_tests: list[TestCasePlan] = []
    for test in plan.tests:
        ok = True
        for step in test.steps:
            if step.target_element_id and step.target_element_id not in valid_element_ids:
                logger.warning(
                    "test_planner.dropped_invalid_element_ref",
                    test_id=test.id,
                    element_id=step.target_element_id,
                )
                ok = False
                break
        if ok:
            valid_tests.append(test)
    return valid_tests


async def generate_test_plan(
    db: Session,
    *,
    provider: LLMProvider,
    application_id: str,
    application_model: ApplicationModel,
    max_tests: int,
    test_run_id: str | None = None,
) -> list[TestCase]:
    system_prompt = TEST_PLANNER_SYSTEM_PROMPT
    task_prompt = build_test_planning_task_prompt(application_model.model_dump(mode="json"), max_tests)

    requested_at = datetime.now(UTC)
    result = await provider.generate_test_plan(
        application_model=application_model.model_dump(mode="json"),
        max_tests=max_tests,
        system_prompt=system_prompt,
        task_prompt=task_prompt,
    )

    ai_request = AIRequest(
        test_run_id=test_run_id,
        operation="generate_test_plan",
        provider=provider.name,
        model=result.model,
        prompt_summary=task_prompt[:500],
        raw_response={"text": result.raw_text[:5000]},
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
        estimated_cost_usd=result.estimated_cost_usd,
        latency_ms=result.latency_ms,
        succeeded=True,
        requested_at=requested_at,
    )

    try:
        parsed = extract_json_object(result.raw_text)
        parsed.setdefault("application_id", application_id)
        plan = TestPlanResponse.model_validate(parsed)
    except (ValidationError, InvalidTestPlanError) as exc:
        ai_request.succeeded = False
        ai_request.error_message = str(exc)[:2000]
        db.add(ai_request)
        db.commit()
        raise InvalidTestPlanError(f"AI test plan failed validation: {exc}") from exc

    valid_element_ids = {e.id for e in application_model.elements}
    validated_tests = _validate_element_references(plan, valid_element_ids)
    validated_tests = validated_tests[:max_tests]

    db.add(ai_request)
    db.flush()

    test_cases: list[TestCase] = []
    for plan_item in validated_tests:
        tc = TestCase(
            application_id=application_id,
            external_code=plan_item.id,
            name=plan_item.name,
            business_intent=plan_item.business_intent,
            category=plan_item.category.value,
            priority=plan_item.priority.value,
            risk=plan_item.risk.value,
            expected_outcome=plan_item.expected,
            rationale=plan_item.rationale,
            assertions=[a.model_dump(mode="json") for a in plan_item.assertions],
            source="ai_generated",
        )
        for step in plan_item.steps:
            tc.steps.append(
                TestStep(
                    order_index=step.order_index,
                    action=step.action.value,
                    target_element_id=step.target_element_id,
                    locator=(step.locator.model_dump(mode="json") if step.locator else {"primary": {"strategy": "css", "value": "body"}}),
                    value=step.value,
                    description=step.description,
                )
            )
        db.add(tc)
        test_cases.append(tc)

    db.commit()
    for tc in test_cases:
        db.refresh(tc)
    return test_cases
