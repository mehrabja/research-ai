"""F02 — persistent sessions and one-time authentication tokens.

Revision ID: 0033
Revises: 0032
Create Date: 2026-09-27

Adds:
- User email verification timestamp.
- Persistent refresh sessions with hashed opaque credentials.
- Single-use password-reset/email-verification token records.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0033"
down_revision: Union[str, None] = "0032"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "email_verified_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    op.create_table(
        "auth_sessions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "last_used_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "revoked_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("ip_address", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "token_hash",
            name="ux_auth_sessions_token_hash",
        ),
    )
    op.create_index(
        "ix_auth_sessions_user_active",
        "auth_sessions",
        ["user_id", "expires_at"],
        postgresql_where=sa.text("revoked_at IS NULL"),
    )
    op.create_index(
        "ix_auth_sessions_user_expires",
        "auth_sessions",
        ["user_id", "expires_at"],
    )

    op.create_table(
        "auth_one_time_tokens",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("purpose", sa.Text(), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "consumed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "token_hash",
            name="ux_auth_one_time_tokens_token_hash",
        ),
    )
    op.create_index(
        "ix_auth_one_time_tokens_user_purpose",
        "auth_one_time_tokens",
        ["user_id", "purpose", "expires_at"],
    )
    op.create_index(
        "ix_auth_one_time_tokens_active",
        "auth_one_time_tokens",
        ["purpose", "expires_at"],
        postgresql_where=sa.text("consumed_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_auth_one_time_tokens_active",
        table_name="auth_one_time_tokens",
    )
    op.drop_index(
        "ix_auth_one_time_tokens_user_purpose",
        table_name="auth_one_time_tokens",
    )
    op.drop_table("auth_one_time_tokens")

    op.drop_index(
        "ix_auth_sessions_user_expires",
        table_name="auth_sessions",
    )
    op.drop_index(
        "ix_auth_sessions_user_active",
        table_name="auth_sessions",
    )
    op.drop_table("auth_sessions")

    op.drop_column("users", "email_verified_at")
