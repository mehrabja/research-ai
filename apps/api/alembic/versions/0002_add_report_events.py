"""add report events

Revision ID: 0002_add_report_events
Revises: 14b3d4303f3f
Create Date: 2026-09-17
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0002_add_report_events"
down_revision: Union[str, None] = "14b3d4303f3f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "report_events",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "report_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("reports.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("from_status", sa.Text(), nullable=True),
        sa.Column("to_status", sa.Text(), nullable=True),
        sa.Column(
            "version_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("report_versions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "event_type IN ('status_transition','version_created')",
            name="ck_report_events_type",
        ),
        sa.CheckConstraint(
            "(event_type = 'status_transition'"
            " AND from_status IS NOT NULL"
            " AND to_status IS NOT NULL"
            " AND from_status <> to_status"
            " AND version_id IS NULL)"
            " OR "
            "(event_type = 'version_created'"
            " AND version_id IS NOT NULL"
            " AND from_status IS NULL"
            " AND to_status IS NULL)",
            name="ck_report_events_shape",
        ),
    )

    op.create_index(
        "ix_report_events_report_created",
        "report_events",
        ["report_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_report_events_report_created",
        table_name="report_events",
    )
    op.drop_table("report_events")