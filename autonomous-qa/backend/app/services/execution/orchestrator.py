"""The core pipeline orchestrator: this is where OBSERVE -> UNDERSTAND ->
DETECT CHANGE -> PREDICT IMPACT -> GENERATE TESTS -> EXECUTE -> ANALYZE
-> HEAL -> RETEST -> LEARN -> EXPLAIN actually happens for one TestRun.

Runs inside a Celery worker (see workers/tasks.py), never inside an HTTP
request handler.
"""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.models.application import Application
from app.models.healing_event import HealingEvent
from app.models.snapshot import ApplicationSnapshot
from app.models.test_result import TestResult
from app.models.test_run import RunStatus, TestRun
from app.repositories.test_cases import list_for_application
from app.schemas.discovery import ApplicationModel, Locator
from app.services.ai.failure_analyzer import analyze_failure
from app.services.ai.groq_provider import get_llm_provider
from app.services.ai.test_generator import generate_and_persist_tests
from app.services.change_intelligence.change_detector import detect_change
from app.services.change_intelligence.impact_analyzer import analyze_impact
from app.services.change_intelligence.snapshot_comparator import compare_snapshots
from app.services.discovery.crawler import discover_application
from app.services.execution.engine import AssertionDefinition, TestDefinition, TestStepDefinition
from app.services.execution.playwright_engine import PlaywrightEngine
from app.services.execution.selenium_engine import SeleniumEngine
from app.services.healing.healer import heal_step
from app.services.reporting.report_generator import build_run_explanation, compute_quality_score
from app.services.risk.risk_engine import RiskInputs, compute_risk
from app.services.run_state_machine import transition

logger = get_logger(__name__)


def _get_engine(name: str):
    return SeleniumEngine() if name == "selenium" else PlaywrightEngine()


def _historical_failure_rate(db: Session, test_case_id) -> float:
    past = (
        db.query(TestResult)
        .filter(TestResult.test_case_id == test_case_id)
        .order_by(TestResult.created_at.desc())
        .limit(10)
        .all()
    )
    if not past:
        return 0.0
    failures = sum(1 for r in past if r.status in ("FAILED", "HEALING_FAILED", "ERROR"))
    return failures / len(past)


def _regression_break_count(db: Session, test_case_id) -> int:
    return db.query(HealingEvent).filter(HealingEvent.test_case_id == test_case_id).count()


async def run_pipeline(db: Session, run: TestRun) -> None:
    settings = get_settings()
    application: Application = db.query(Application).filter(Application.id == run.application_id).first()
    if application is None:
        transition(db, run, RunStatus.FAILED)
        run.error_message = "Application not found."
        db.commit()
        return

    provider = get_llm_provider() if settings.GROQ_API_KEY else None

    application_model: ApplicationModel | None = None
    change = None
    try:
        if run.run_discovery:
            transition(db, run, RunStatus.DISCOVERING)
            application_model = await discover_application(application.base_url)

            prev_snapshot = (
                db.query(ApplicationSnapshot)
                .filter(ApplicationSnapshot.application_id == application.id)
                .order_by(ApplicationSnapshot.sequence_number.desc())
                .first()
            )
            next_seq = (prev_snapshot.sequence_number + 1) if prev_snapshot else 1
            snapshot = ApplicationSnapshot(
                application_id=application.id,
                sequence_number=next_seq,
                root_url=application.base_url,
                title=application_model.application.title,
                application_model=application_model.model_dump(mode="json"),
                element_count=len(application_model.elements),
                page_count=len(application_model.pages),
            )
            db.add(snapshot)
            db.commit()

            if prev_snapshot is not None:
                previous_model = ApplicationModel.model_validate(prev_snapshot.application_model)
                diff = compare_snapshots(previous_model, application_model)
                change = detect_change(diff)
        else:
            latest_snapshot = (
                db.query(ApplicationSnapshot)
                .filter(ApplicationSnapshot.application_id == application.id)
                .order_by(ApplicationSnapshot.sequence_number.desc())
                .first()
            )
            if latest_snapshot:
                application_model = ApplicationModel.model_validate(latest_snapshot.application_model)
    except AppError as exc:
        transition(db, run, RunStatus.FAILED)
        run.error_message = str(exc)
        db.commit()
        return

    all_test_cases = list_for_application(db, str(application.id))
    impacted_ids: set[str] = set()
    if change is not None:
        impact = analyze_impact(change, all_test_cases)
        impacted_ids = impact.impacted_ids

    try:
        if run.run_generation and application_model is not None:
            if provider is None:
                raise AppError("GROQ_API_KEY is not configured; cannot generate tests.")
            transition(db, run, RunStatus.PLANNING)
            transition(db, run, RunStatus.GENERATING)
            new_tests = await generate_and_persist_tests(
                db,
                provider=provider,
                application_id=str(application.id),
                application_model=application_model,
                max_tests=run.max_tests,
                test_run_id=str(run.id),
            )
            transition(db, run, RunStatus.VALIDATING)
            run.tests_generated = len(new_tests)
            db.commit()
            tests_to_run = new_tests
        elif run.single_test_case_id is not None:
            tests_to_run = [tc for tc in all_test_cases if tc.id == run.single_test_case_id]
            run.tests_generated = len(tests_to_run)
            db.commit()
        else:
            tests_to_run = all_test_cases[: run.max_tests]
            run.tests_generated = len(tests_to_run)
            db.commit()
    except AppError as exc:
        transition(db, run, RunStatus.FAILED)
        run.error_message = str(exc)
        db.commit()
        return

    if impacted_ids:
        impacted_tests = [tc for tc in all_test_cases if str(tc.id) in impacted_ids]
        selected_ids = {str(tc.id) for tc in tests_to_run}
        for tc in impacted_tests:
            if str(tc.id) not in selected_ids and len(tests_to_run) < run.max_tests:
                tests_to_run.append(tc)

    transition(db, run, RunStatus.EXECUTING)
    engine = _get_engine(application.browser_engine)
    healing_confidences: list[float] = []
    any_healed = False
    failure_details: list[str] = []
    high_risk_executed = 0
    high_risk_passed = 0

    for tc in tests_to_run:
        heal_records: list[dict] = []

        async def healing_callback(page, step: TestStepDefinition, _records=heal_records):
            result = await heal_step(page, step, ai_provider=provider, db=db, test_run_id=str(run.id))
            _records.append(result)
            if result.get("outcome") == "HEALED":
                return result
            return None

        step_defs = [
            TestStepDefinition(
                order_index=s.order_index,
                action=s.action,
                target_element_id=s.target_element_id,
                locator=Locator.model_validate(s.locator) if s.locator else None,
                value=s.value,
                description=s.description,
            )
            for s in sorted(tc.steps, key=lambda x: x.order_index)
        ]
        assertion_defs = [
            AssertionDefinition(
                type=a.get("type"),
                expected_value=a.get("expected_value"),
                locator=Locator.model_validate(a["locator"]) if a.get("locator") else None,
            )
            for a in tc.assertions
        ]
        test_def = TestDefinition(
            test_case_id=str(tc.id),
            name=tc.name,
            steps=step_defs,
            assertions=assertion_defs,
            base_url=application.base_url,
        )

        exec_result = await engine.run_test(
            test_def,
            headless=settings.BROWSER_HEADLESS,
            timeout_ms=settings.BROWSER_TIMEOUT_MS,
            healing_callback=healing_callback if settings.HEALING_ENABLED else None,
        )

        result_row = TestResult(
            test_run_id=run.id,
            test_case_id=tc.id,
            status=exec_result.status,
            engine=engine.name,
            started_at=datetime.now(UTC),
            finished_at=datetime.now(UTC),
            duration_ms=exec_result.duration_ms,
            step_results=[r.__dict__ for r in exec_result.step_results],
            error_message=exec_result.error_message,
            screenshot_path=exec_result.screenshot_path,
            trace_path=exec_result.trace_path,
            console_logs=exec_result.console_logs,
            network_failures=exec_result.network_failures,
        )

        verification_result = "PASSED" if exec_result.status in ("PASSED", "HEALED") else "FAILED"
        for record in heal_records:
            outcome = record["outcome"]
            if exec_result.status == "FAILED" and outcome == "HEALED":
                outcome = "HEALING_FAILED"
            event = HealingEvent(
                test_run_id=run.id,
                test_case_id=tc.id,
                original_locator=(
                    step_defs[0].locator.model_dump(mode="json") if step_defs and step_defs[0].locator else {}
                ),
                replacement_locator=record.get("replacement_locator"),
                candidates_considered=record.get("candidates_considered", []),
                confidence=record.get("confidence", 0.0),
                method=record.get("method", "deterministic"),
                reason=record.get("reason", ""),
                outcome=outcome,
                verification_result=verification_result if record["outcome"] == "HEALED" else None,
                healed_at=datetime.now(UTC) if outcome == "HEALED" else None,
            )
            db.add(event)
            if outcome == "HEALED":
                any_healed = True
                healing_confidences.append(record.get("confidence", 0.0))

        change_magnitude = 1.0 if str(tc.id) in impacted_ids else 0.0
        risk = compute_risk(
            RiskInputs(
                business_intent=(tc.business_intent.split()[0].upper() if tc.business_intent else tc.category),
                change_magnitude=change_magnitude,
                historical_failure_rate=_historical_failure_rate(db, tc.id),
                regression_break_count=_regression_break_count(db, tc.id),
            )
        )
        result_row.risk_score = risk.score
        result_row.risk_level = risk.level

        if risk.level in ("HIGH", "CRITICAL"):
            high_risk_executed += 1
            if exec_result.status in ("PASSED", "HEALED"):
                high_risk_passed += 1

        if exec_result.status == "FAILED" and provider is not None:
            if run.status != RunStatus.ANALYZING:
                transition(db, run, RunStatus.ANALYZING)
            analysis = await analyze_failure(
                db,
                provider=provider,
                context={
                    "test_name": tc.name,
                    "error_message": exec_result.error_message,
                    "step_results": [r.__dict__ for r in exec_result.step_results],
                },
                test_run_id=str(run.id),
            )
            result_row.ai_explanation = analysis.explanation
            failure_details.append(f"'{tc.name}' failed: {analysis.explanation}")
        elif exec_result.status == "FAILED":
            failure_details.append(f"'{tc.name}' failed: {exec_result.error_message}")

        db.add(result_row)
        db.commit()

    if any_healed:
        transition(db, run, RunStatus.HEALING)
        transition(db, run, RunStatus.RETESTING)

    results = db.query(TestResult).filter(TestResult.test_run_id == run.id).all()
    run.tests_executed = len(results)
    run.tests_passed = sum(1 for r in results if r.status == "PASSED")
    run.tests_failed = sum(1 for r in results if r.status in ("FAILED", "ERROR"))
    run.tests_healed = sum(1 for r in results if r.status == "HEALED")
    run.tests_review_required = (
        db.query(HealingEvent)
        .filter(HealingEvent.test_run_id == run.id, HealingEvent.outcome == "REVIEW_REQUIRED")
        .count()
    )

    quality = compute_quality_score(
        tests_executed=run.tests_executed,
        tests_passed=run.tests_passed,
        tests_healed=run.tests_healed,
        tests_failed=run.tests_failed,
        critical_failures=sum(
            1 for r in results if r.status in ("FAILED", "ERROR") and r.risk_level == "CRITICAL"
        ),
        high_risk_executed=high_risk_executed,
        high_risk_passed=high_risk_passed,
        healing_confidences=healing_confidences,
    )
    run.quality_score = quality.score if quality.score >= 0 else None
    run.quality_score_breakdown = quality.factors

    explanation = build_run_explanation(
        change_summary=change.summary if change else "No prior snapshot to compare against.",
        impacted_count=len(impacted_ids),
        passed=run.tests_passed,
        failed=run.tests_failed,
        healed=run.tests_healed,
        review_required=run.tests_review_required,
        failure_details=failure_details,
    )
    run.ai_explanation = explanation

    transition(db, run, RunStatus.COMPLETED)
    db.commit()
