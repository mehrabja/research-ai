"""M35 — Agentic orchestration.

Revision ID: 0030
Revises: 0029
Create Date: 2026-09-25

Non-destructive: creates two new tables.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0030"
down_revision = "0029"
branch_labels = None
depends_on = None


def _in_check(col: str, values: tuple[str, ...]) -> str:
    return f"{col} IN (" + ",".join(f"'{v}'" for v in values) + ")"


RUN_STATUSES = (
    "queued", "planning", "awaiting_approval", "executing",
    "paused", "blocked", "completed", "failed", "cancelled",
)
NODE_STATUSES = (
    "pending", "running", "awaiting_approval",
    "completed", "failed", "skipped", "blocked",
)
NODE_TYPES = ("deterministic", "model_assisted", "human_approval")
FAILURE_CLASSES = (
    "validation", "not_found", "conflict", "ownership",
    "unsupported", "provider_retryable", "provider_permanent",
    "timeout", "budget_exceeded", "stale_worker", "internal",
)


def upgrade() -> None:
    op.create_table(
        "research_orchestration_runs",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "project_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "report_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("reports.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("goal", sa.Text(), nullable=False),
        sa.Column("goal_meta", postgresql.JSONB(), nullable=True),
        sa.Column("context_hash", sa.Text(), nullable=False),
        sa.Column(
            "orchestration_version", sa.Text(), nullable=False,
        ),
        sa.Column("planner_version", sa.Text(), nullable=False),
        sa.Column(
            "tool_registry_version", sa.Text(), nullable=False,
        ),
        sa.Column("strategy", sa.Text(), nullable=False),
        sa.Column(
            "status", sa.Text(),
            server_default=sa.text("'queued'"), nullable=False,
        ),
        sa.Column("current_node_key", sa.Text(), nullable=True),
        sa.Column("budget", postgresql.JSONB(), nullable=False),
        sa.Column("budget_used", postgresql.JSONB(), nullable=True),
        sa.Column(
            "approvals_required", postgresql.JSONB(), nullable=True,
        ),
        sa.Column(
            "approvals_received", postgresql.JSONB(), nullable=True,
        ),
        sa.Column("summary", postgresql.JSONB(), nullable=True),
        sa.Column("errors", postgresql.JSONB(), nullable=True),
        sa.Column(
            "checkpoint_state", postgresql.JSONB(), nullable=True,
        ),
        sa.Column(
            "last_checkpoint_at", sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "node_count", sa.Integer(),
            server_default=sa.text("0"), nullable=False,
        ),
        sa.Column(
            "completed_node_count", sa.Integer(),
            server_default=sa.text("0"), nullable=False,
        ),
        sa.Column(
            "failed_node_count", sa.Integer(),
            server_default=sa.text("0"), nullable=False,
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column(
            "started_at", sa.DateTime(timezone=True), nullable=True,
        ),
        sa.Column(
            "completed_at", sa.DateTime(timezone=True), nullable=True,
        ),
        sa.Column(
            "failed_at", sa.DateTime(timezone=True), nullable=True,
        ),
        sa.Column(
            "cancelled_at", sa.DateTime(timezone=True), nullable=True,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.CheckConstraint(
            _in_check("status", RUN_STATUSES),
            name="ck_orchestration_runs_status",
        ),
        sa.CheckConstraint(
            "node_count >= 0 AND completed_node_count >= 0 AND "
            "failed_node_count >= 0",
            name="ck_orchestration_runs_counts",
        ),
        sa.CheckConstraint(
            "duration_ms IS NULL OR duration_ms >= 0",
            name="ck_orchestration_runs_duration",
        ),
    )
    op.create_index(
        "ix_orchestration_runs_project",
        "research_orchestration_runs", ["project_id"],
    )
    op.create_index(
        "ix_orchestration_runs_report",
        "research_orchestration_runs", ["report_id"],
    )
    op.create_index(
        "ix_orchestration_runs_status",
        "research_orchestration_runs", ["status"],
    )
    op.create_index(
        "ux_orchestration_runs_completed",
        "research_orchestration_runs",
        ["report_id", "context_hash", "orchestration_version"],
        unique=True,
        postgresql_where=sa.text("status = 'completed'"),
    )

    op.create_table(
        "research_orchestration_nodes",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "run_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "research_orchestration_runs.id", ondelete="CASCADE",
            ),
            nullable=False,
        ),
        sa.Column(
            "project_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "report_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("reports.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("node_key", sa.Text(), nullable=False),
        sa.Column("node_version", sa.Text(), nullable=False),
        sa.Column("node_type", sa.Text(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("depends_on", postgresql.JSONB(), nullable=True),
        sa.Column(
            "status", sa.Text(),
            server_default=sa.text("'pending'"), nullable=False,
        ),
        sa.Column("input_snapshot", postgresql.JSONB(), nullable=True),
        sa.Column("output_snapshot", postgresql.JSONB(), nullable=True),
        sa.Column("context_hash", sa.Text(), nullable=False),
        sa.Column(
            "attempt", sa.Integer(),
            server_default=sa.text("0"), nullable=False,
        ),
        sa.Column(
            "max_attempts", sa.Integer(),
            server_default=sa.text("3"), nullable=False,
        ),
        sa.Column(
            "deterministic", sa.Boolean(),
            server_default=sa.text("true"), nullable=False,
        ),
        sa.Column("error_class", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "checkpoint_meta", postgresql.JSONB(), nullable=True,
        ),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column(
            "started_at", sa.DateTime(timezone=True), nullable=True,
        ),
        sa.Column(
            "completed_at", sa.DateTime(timezone=True), nullable=True,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.CheckConstraint(
            _in_check("status", NODE_STATUSES),
            name="ck_orchestration_nodes_status",
        ),
        sa.CheckConstraint(
            _in_check("node_type", NODE_TYPES),
            name="ck_orchestration_nodes_type",
        ),
        sa.CheckConstraint(
            "error_class IS NULL OR " +
            _in_check("error_class", FAILURE_CLASSES),
            name="ck_orchestration_nodes_error_class",
        ),
        sa.CheckConstraint(
            "sequence >= 0",
            name="ck_orchestration_nodes_sequence",
        ),
        sa.CheckConstraint(
            "attempt >= 0 AND max_attempts >= 1",
            name="ck_orchestration_nodes_attempt",
        ),
        sa.CheckConstraint(
            "attempt <= max_attempts",
            name="ck_orchestration_nodes_attempt_max",
        ),
        sa.CheckConstraint(
            "duration_ms IS NULL OR duration_ms >= 0",
            name="ck_orchestration_nodes_duration",
        ),
        sa.UniqueConstraint(
            "run_id", "node_key", "node_version", "context_hash",
            name="ux_orchestration_nodes_idempotency",
        ),
    )
    op.create_index(
        "ix_orchestration_nodes_run_sequence",
        "research_orchestration_nodes", ["run_id", "sequence"],
    )
    op.create_index(
        "ix_orchestration_nodes_run_status",
        "research_orchestration_nodes", ["run_id", "status"],
    )
    op.create_index(
        "ix_orchestration_nodes_project",
        "research_orchestration_nodes", ["project_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_orchestration_nodes_project",
        table_name="research_orchestration_nodes",
    )
    op.drop_index(
        "ix_orchestration_nodes_run_status",
        table_name="research_orchestration_nodes",
    )
    op.drop_index(
        "ix_orchestration_nodes_run_sequence",
        table_name="research_orchestration_nodes",
    )
    op.drop_table("research_orchestration_nodes")

    op.drop_index(
        "ux_orchestration_runs_completed",
        table_name="research_orchestration_runs",
    )
    op.drop_index(
        "ix_orchestration_runs_status",
        table_name="research_orchestration_runs",
    )
    op.drop_index(
        "ix_orchestration_runs_report",
        table_name="research_orchestration_runs",
    )
    op.drop_index(
        "ix_orchestration_runs_project",
        table_name="research_orchestration_runs",
    )
    op.drop_table("research_orchestration_runs")