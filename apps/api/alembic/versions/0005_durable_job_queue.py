"""add durable job queue

Revision ID: 0005_durable_job_queue
Revises: 0004_chunk_embedding_lifecycle
Create Date: 2026-09-17

Drops the M1 placeholder ``jobs`` table (empty and unused) and
recreates it with the M10 durable-queue shape.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0005_durable_job_queue"
down_revision: Union[str, None] = "0004_chunk_embedding_lifecycle"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DROP TABLE IF EXISTS jobs CASCADE")

    op.create_table(
        "jobs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("job_type", sa.Text(), nullable=False),
        sa.Column(
            "status", sa.Text(), nullable=False,
            server_default=sa.text("'queued'"),
        ),
        sa.Column(
            "priority", sa.Integer(), nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "payload", postgresql.JSONB(), nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "report_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("reports.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "user_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "attempt_count", sa.Integer(), nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "max_attempts", sa.Integer(), nullable=False,
            server_default=sa.text("3"),
        ),
        sa.Column(
            "available_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.text("now()"),
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("worker_id", sa.Text(), nullable=True),
        sa.Column("last_error_code", sa.Text(), nullable=True),
        sa.Column("last_error_message", sa.Text(), nullable=True),
        sa.Column("idempotency_key", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "status IN ("
            "'queued','processing','retrying','completed',"
            "'failed','cancelled')",
            name="ck_jobs_status",
        ),
        sa.CheckConstraint("priority >= 0", name="ck_jobs_priority_nonneg"),
        sa.CheckConstraint(
            "attempt_count >= 0", name="ck_jobs_attempt_count_nonneg"
        ),
        sa.CheckConstraint(
            "max_attempts >= 1", name="ck_jobs_max_attempts_pos"
        ),
        sa.CheckConstraint(
            "attempt_count <= max_attempts",
            name="ck_jobs_attempt_within_max",
        ),
        sa.CheckConstraint(
            "status <> 'processing' OR "
            "(worker_id IS NOT NULL AND "
            "heartbeat_at IS NOT NULL AND "
            "started_at IS NOT NULL)",
            name="ck_jobs_processing_lease",
        ),
        sa.CheckConstraint(
            "status <> 'completed' OR completed_at IS NOT NULL",
            name="ck_jobs_completed_at_required",
        ),
        sa.CheckConstraint(
            "status <> 'failed' OR failed_at IS NOT NULL",
            name="ck_jobs_failed_at_required",
        ),
    )

    op.create_index(
        "ix_jobs_ready", "jobs",
        ["status", "available_at", "priority", "created_at"],
        postgresql_where=sa.text("status IN ('queued', 'retrying')"),
    )
    op.create_index("ix_jobs_report", "jobs", ["report_id"])
    op.create_index(
        "ix_jobs_stale", "jobs", ["status", "heartbeat_at"],
        postgresql_where=sa.text("status = 'processing'"),
    )
    op.create_index(
        "ix_jobs_user_created", "jobs", ["user_id", "created_at"]
    )
    op.create_index(
        "ux_jobs_idempotency_key", "jobs", ["idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS jobs CASCADE")
    op.execute(
        "CREATE TABLE jobs ("
        " id UUID PRIMARY KEY DEFAULT gen_random_uuid(),"
        " report_id UUID REFERENCES reports(id) ON DELETE CASCADE,"
        " phase TEXT NOT NULL,"
        " status TEXT NOT NULL,"
        " retry_count INTEGER NOT NULL DEFAULT 0,"
        " error_message TEXT,"
        " idempotency_key TEXT UNIQUE,"
        " trace_id TEXT,"
        " started_at TIMESTAMPTZ,"
        " completed_at TIMESTAMPTZ,"
        " created_at TIMESTAMPTZ NOT NULL DEFAULT now(),"
        " CONSTRAINT ck_jobs_status CHECK ("
        "  status IN ('pending','running','success','failed',"
        "             'cancelled','retrying')),"
        " CONSTRAINT ck_jobs_retry_count CHECK (retry_count >= 0))"
    )
    op.execute(
        "CREATE INDEX ix_jobs_status_created ON jobs (status, created_at)"
    )
    op.execute("CREATE INDEX ix_jobs_report ON jobs (report_id)")
    op.execute("CREATE INDEX ix_jobs_trace_id ON jobs (trace_id)")