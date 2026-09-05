"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-01-01 00:00:00

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

_RUN_STATUS_VALUES = (
    "CREATED", "QUEUED", "DISCOVERING", "PLANNING", "GENERATING", "VALIDATING",
    "EXECUTING", "ANALYZING", "HEALING", "RETESTING", "COMPLETED", "FAILED", "CANCELLED",
)
run_status_enum = pg.ENUM(*_RUN_STATUS_VALUES, name="run_status", create_type=False)


def upgrade() -> None:
    # Use a DO block so Postgres handles IF NOT EXISTS atomically,
    # which works correctly even inside a transactional DDL session.
    op.execute(
        "DO $$ BEGIN "
        "  CREATE TYPE run_status AS ENUM ("
        + ", ".join(f"'{v}'" for v in _RUN_STATUS_VALUES)
        + "  ); "
        "EXCEPTION WHEN duplicate_object THEN NULL; "
        "END $$;"
    )

    op.create_table(
        "projects",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_projects_name", "projects", ["name"])

    op.create_table(
        "applications",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", pg.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("base_url", sa.String(2048), nullable=False),
        sa.Column("browser_engine", sa.String(50), nullable=False, server_default="playwright"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_applications_project_id", "applications", ["project_id"])

    op.create_table(
        "application_snapshots",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("application_id", pg.UUID(as_uuid=True), sa.ForeignKey("applications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("root_url", sa.String(2048), nullable=False),
        sa.Column("title", sa.String(1024), nullable=True),
        sa.Column("application_model", pg.JSONB(), nullable=False),
        sa.Column("element_count", sa.Integer(), server_default="0"),
        sa.Column("page_count", sa.Integer(), server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_application_snapshots_application_id", "application_snapshots", ["application_id"])

    op.create_table(
        "test_cases",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("application_id", pg.UUID(as_uuid=True), sa.ForeignKey("applications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("external_code", sa.String(50), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("business_intent", sa.Text(), nullable=False),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("priority", sa.String(20), nullable=False),
        sa.Column("risk", sa.String(20), nullable=False),
        sa.Column("expected_outcome", sa.Text(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("assertions", pg.JSONB(), server_default="[]"),
        sa.Column("source", sa.String(20), server_default="ai_generated"),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_test_cases_application_id", "test_cases", ["application_id"])

    op.create_table(
        "test_steps",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("test_case_id", pg.UUID(as_uuid=True), sa.ForeignKey("test_cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("target_element_id", sa.String(255), nullable=True),
        sa.Column("locator", pg.JSONB(), nullable=False),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_test_steps_test_case_id", "test_steps", ["test_case_id"])

    op.create_table(
        "test_runs",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("application_id", pg.UUID(as_uuid=True), sa.ForeignKey("applications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", run_status_enum, nullable=False, server_default="CREATED"),
        sa.Column("trigger", sa.String(50), server_default="manual"),
        sa.Column("run_discovery", sa.Boolean(), server_default=sa.true()),
        sa.Column("run_generation", sa.Boolean(), server_default=sa.true()),
        sa.Column("max_tests", sa.Integer(), server_default="25"),
        sa.Column("single_test_case_id", pg.UUID(as_uuid=True), sa.ForeignKey("test_cases.id", ondelete="SET NULL"), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("timeout_seconds", sa.Integer(), server_default="900"),
        sa.Column("tests_generated", sa.Integer(), server_default="0"),
        sa.Column("tests_executed", sa.Integer(), server_default="0"),
        sa.Column("tests_passed", sa.Integer(), server_default="0"),
        sa.Column("tests_failed", sa.Integer(), server_default="0"),
        sa.Column("tests_healed", sa.Integer(), server_default="0"),
        sa.Column("tests_review_required", sa.Integer(), server_default="0"),
        sa.Column("quality_score", sa.Integer(), nullable=True),
        sa.Column("quality_score_breakdown", pg.JSONB(), nullable=True),
        sa.Column("ai_explanation", pg.JSONB(), nullable=True),
        sa.Column("error_message", sa.String(2048), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_test_runs_application_id", "test_runs", ["application_id"])
    op.create_index("ix_test_runs_status", "test_runs", ["status"])
    op.create_index("ix_test_runs_created_at", "test_runs", ["created_at"])

    op.create_table(
        "test_results",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("test_run_id", pg.UUID(as_uuid=True), sa.ForeignKey("test_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("test_case_id", pg.UUID(as_uuid=True), sa.ForeignKey("test_cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("engine", sa.String(20), server_default="playwright"),
        sa.Column("browser", sa.String(20), server_default="chromium"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("step_results", pg.JSONB(), server_default="[]"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("screenshot_path", sa.String(1024), nullable=True),
        sa.Column("trace_path", sa.String(1024), nullable=True),
        sa.Column("console_logs", pg.JSONB(), server_default="[]"),
        sa.Column("network_failures", pg.JSONB(), server_default="[]"),
        sa.Column("risk_score", sa.Float(), nullable=True),
        sa.Column("risk_level", sa.String(20), nullable=True),
        sa.Column("ai_explanation", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_test_results_test_run_id", "test_results", ["test_run_id"])
    op.create_index("ix_test_results_test_case_id", "test_results", ["test_case_id"])
    op.create_index("ix_test_results_status", "test_results", ["status"])

    op.create_table(
        "healing_events",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("test_run_id", pg.UUID(as_uuid=True), sa.ForeignKey("test_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("test_case_id", pg.UUID(as_uuid=True), sa.ForeignKey("test_cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("test_step_id", pg.UUID(as_uuid=True), sa.ForeignKey("test_steps.id", ondelete="SET NULL"), nullable=True),
        sa.Column("original_locator", pg.JSONB(), nullable=False),
        sa.Column("replacement_locator", pg.JSONB(), nullable=True),
        sa.Column("candidates_considered", pg.JSONB(), server_default="[]"),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("method", sa.String(30), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("outcome", sa.String(30), nullable=False),
        sa.Column("verification_result", sa.String(30), nullable=True),
        sa.Column("healed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_healing_events_test_run_id", "healing_events", ["test_run_id"])
    op.create_index("ix_healing_events_test_case_id", "healing_events", ["test_case_id"])
    op.create_index("ix_healing_events_outcome", "healing_events", ["outcome"])

    op.create_table(
        "ai_requests",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("test_run_id", pg.UUID(as_uuid=True), sa.ForeignKey("test_runs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("operation", sa.String(50), nullable=False),
        sa.Column("provider", sa.String(30), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("prompt_summary", sa.Text(), nullable=False),
        sa.Column("raw_response", pg.JSONB(), nullable=True),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.Column("estimated_cost_usd", sa.Float(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("succeeded", sa.Boolean(), server_default=sa.true()),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_ai_requests_test_run_id", "ai_requests", ["test_run_id"])

    op.create_table(
        "audit_logs",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("actor", sa.String(255), server_default="system"),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("resource_type", sa.String(50), nullable=False),
        sa.Column("resource_id", pg.UUID(as_uuid=True), nullable=True),
        sa.Column("request_id", sa.String(64), nullable=True),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("metadata_json", pg.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_resource_id", "audit_logs", ["resource_id"])
    op.create_index("ix_audit_logs_request_id", "audit_logs", ["request_id"])


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("ai_requests")
    op.drop_table("healing_events")
    op.drop_table("test_results")
    op.drop_table("test_runs")
    op.drop_table("test_steps")
    op.drop_table("test_cases")
    op.drop_table("application_snapshots")
    op.drop_table("applications")
    op.drop_table("projects")
    run_status_enum.drop(op.get_bind(), checkfirst=True)
