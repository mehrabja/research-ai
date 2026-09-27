"""M39 — auditable provider-operation ledger."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0034"
down_revision = "0033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "provider_operations",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "report_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("reports.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("jobs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("request_id", sa.Text(), nullable=True),
        sa.Column("operation", sa.Text(), nullable=False),
        sa.Column("capability", sa.Text(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("model", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("input_tokens", sa.BigInteger(), nullable=True),
        sa.Column("output_tokens", sa.BigInteger(), nullable=True),
        sa.Column("total_tokens", sa.BigInteger(), nullable=True),
        sa.Column("duration_ms", sa.BigInteger(), nullable=True),
        sa.Column("cost_raw_usd", sa.Numeric(18, 8), nullable=True),
        sa.Column("cost_billable_usd", sa.Numeric(18, 8), nullable=True),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("idempotency_key", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "capability IN ('generation','embedding','translation','detection','search','reranking')",
            name="ck_provider_operations_capability",
        ),
        sa.CheckConstraint(
            "status IN ('started','succeeded','failed','canceled')",
            name="ck_provider_operations_status",
        ),
        sa.CheckConstraint(
            "input_tokens IS NULL OR input_tokens >= 0",
            name="ck_provider_operations_input_tokens",
        ),
        sa.CheckConstraint(
            "output_tokens IS NULL OR output_tokens >= 0",
            name="ck_provider_operations_output_tokens",
        ),
        sa.CheckConstraint(
            "total_tokens IS NULL OR total_tokens >= 0",
            name="ck_provider_operations_total_tokens",
        ),
        sa.CheckConstraint(
            "duration_ms IS NULL OR duration_ms >= 0",
            name="ck_provider_operations_duration",
        ),
        sa.CheckConstraint(
            "cost_raw_usd IS NULL OR cost_raw_usd >= 0",
            name="ck_provider_operations_cost_raw",
        ),
        sa.CheckConstraint(
            "cost_billable_usd IS NULL OR cost_billable_usd >= 0",
            name="ck_provider_operations_cost_billable",
        ),
        sa.UniqueConstraint(
            "workspace_id",
            "idempotency_key",
            name="ux_provider_operations_workspace_idempotency",
        ),
    )
    op.create_index(
        "ix_provider_operations_workspace_started",
        "provider_operations",
        ["workspace_id", "started_at"],
    )
    op.create_index(
        "ix_provider_operations_workspace_operation",
        "provider_operations",
        ["workspace_id", "operation", "started_at"],
    )
    op.create_index(
        "ix_provider_operations_provider_model",
        "provider_operations",
        ["provider", "model", "started_at"],
    )
    op.create_index(
        "ix_provider_operations_job",
        "provider_operations",
        ["job_id"],
    )
    op.create_index(
        "ix_provider_operations_request",
        "provider_operations",
        ["request_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_provider_operations_request", table_name="provider_operations")
    op.drop_index("ix_provider_operations_job", table_name="provider_operations")
    op.drop_index("ix_provider_operations_provider_model", table_name="provider_operations")
    op.drop_index("ix_provider_operations_workspace_operation", table_name="provider_operations")
    op.drop_index("ix_provider_operations_workspace_started", table_name="provider_operations")
    op.drop_table("provider_operations")
