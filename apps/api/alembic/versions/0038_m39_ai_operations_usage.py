"""M39 F01 — AI operation ledger and usage classification."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0038"
down_revision = "0037"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_operations",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="SET NULL"), nullable=True),
        sa.Column("report_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("reports.id", ondelete="SET NULL"), nullable=True),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("request_id", sa.Text(), nullable=True),
        sa.Column("operation", sa.Text(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=True),
        sa.Column("model", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), server_default=sa.text("'started'"), nullable=False),
        sa.Column("input_units", sa.Integer(), nullable=True),
        sa.Column("output_units", sa.Integer(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("estimated_cost_usd", sa.Numeric(18, 8), nullable=True),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("idempotency_key", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "status IN ('started','succeeded','failed')",
            name="ck_ai_operations_status",
        ),
        sa.CheckConstraint(
            "input_units IS NULL OR input_units >= 0",
            name="ck_ai_operations_input_nonneg",
        ),
        sa.CheckConstraint(
            "output_units IS NULL OR output_units >= 0",
            name="ck_ai_operations_output_nonneg",
        ),
        sa.CheckConstraint(
            "duration_ms IS NULL OR duration_ms >= 0",
            name="ck_ai_operations_duration_nonneg",
        ),
        sa.UniqueConstraint(
            "workspace_id", "operation", "idempotency_key",
            name="ux_ai_operations_idempotency",
        ),
    )
    op.create_index("ix_ai_operations_workspace_created", "ai_operations", ["workspace_id", "created_at"])
    op.create_index("ix_ai_operations_report_created", "ai_operations", ["report_id", "created_at"])
    op.create_index("ix_ai_operations_job", "ai_operations", ["job_id"])
    op.add_column(
        "usage_events",
        sa.Column("usage_class", sa.Text(), server_default=sa.text("'internal'"), nullable=False),
    )
    op.create_check_constraint(
        "ck_usage_events_class",
        "usage_events",
        "usage_class IN ('provider','internal','billable')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_usage_events_class", "usage_events", type_="check")
    op.drop_column("usage_events", "usage_class")
    op.drop_index("ix_ai_operations_job", table_name="ai_operations")
    op.drop_index("ix_ai_operations_report_created", table_name="ai_operations")
    op.drop_index("ix_ai_operations_workspace_created", table_name="ai_operations")
    op.drop_table("ai_operations")
