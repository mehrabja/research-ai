"""F11 — transactional email delivery records.

Revision ID: 0041
Revises: 0040
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0041"
down_revision: Union[str, None] = "0040"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "email_deliveries",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("to_email", sa.Text(), nullable=False),
        sa.Column("template", sa.Text(), nullable=False),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("provider_message_id", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column(
            "attempt_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "idempotency_key",
            name="ux_email_deliveries_idempotency_key",
        ),
    )
    op.create_index(
        "ix_email_deliveries_status_created",
        "email_deliveries",
        ["status", "created_at"],
    )
    op.create_index(
        "ix_email_deliveries_user_created",
        "email_deliveries",
        ["user_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_email_deliveries_user_created",
        table_name="email_deliveries",
    )
    op.drop_index(
        "ix_email_deliveries_status_created",
        table_name="email_deliveries",
    )
    op.drop_table("email_deliveries")
