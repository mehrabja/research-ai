"""add detection identity columns

Revision ID: 0006_detection_identity
Revises: 0005_durable_job_queue
Create Date: 2026-09-17
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0006_detection_identity"
down_revision: Union[str, None] = "0005_durable_job_queue"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "detection_runs",
        sa.Column(
            "version_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "report_versions.id", ondelete="RESTRICT"
            ),
            nullable=True,
        ),
    )
    op.add_column(
        "detection_runs",
        sa.Column("profile_id", sa.Text(), nullable=True),
    )
    op.add_column(
        "detection_runs",
        sa.Column("input_hash", sa.Text(), nullable=True),
    )
    op.add_column(
        "detection_runs",
        sa.Column("input_chars", sa.Integer(), nullable=True),
    )

    # Replace the status CHECK: 'success'/'partial' were M1 placeholders;
    # M13 uses 'completed'.
    op.drop_constraint(
        "ck_detection_runs_status",
        "detection_runs",
        type_="check",
    )
    op.create_check_constraint(
        "ck_detection_runs_status",
        "detection_runs",
        "status IN ('pending','running','completed','failed')",
    )

    op.create_check_constraint(
        "ck_detection_runs_input_chars",
        "detection_runs",
        "input_chars IS NULL OR input_chars >= 0",
    )

    op.create_index(
        "ux_detection_runs_identity",
        "detection_runs",
        ["report_id", "version_id", "profile_id", "input_hash"],
        unique=True,
        postgresql_where=sa.text("status = 'completed'"),
    )


def downgrade() -> None:
    op.drop_index(
        "ux_detection_runs_identity", table_name="detection_runs"
    )
    op.drop_constraint(
        "ck_detection_runs_input_chars",
        "detection_runs",
        type_="check",
    )
    op.drop_constraint(
        "ck_detection_runs_status",
        "detection_runs",
        type_="check",
    )
    op.create_check_constraint(
        "ck_detection_runs_status",
        "detection_runs",
        "status IN ('pending','running','success','partial','failed')",
    )
    op.drop_column("detection_runs", "input_chars")
    op.drop_column("detection_runs", "input_hash")
    op.drop_column("detection_runs", "profile_id")
    op.drop_column("detection_runs", "version_id")