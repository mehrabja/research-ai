"""add report soft delete

Revision ID: 14b3d4303f3f
Revises: 0001_initial_schema
Create Date: 2026-09-16
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "14b3d4303f3f"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "reports",
        sa.Column(
            "deleted_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    op.create_index(
        "ix_reports_user_active",
        "reports",
        ["user_id", "updated_at", "created_at"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_reports_user_active",
        table_name="reports",
    )

    op.drop_column(
        "reports",
        "deleted_at",
    )