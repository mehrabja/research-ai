"""M39 — persistent authentication sessions and one-time auth tokens."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0033"
down_revision = "0032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_users_email_verified",
        "users",
        ["email_verified_at"],
    )

    op.create_table(
        "user_sessions",
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
        sa.Column("refresh_token_hash", sa.Text(), nullable=False),
        sa.Column(
            "family_id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("ip_address", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "char_length(refresh_token_hash) = 64",
            name="ck_user_sessions_refresh_hash_len",
        ),
        sa.UniqueConstraint(
            "refresh_token_hash",
            name="ux_user_sessions_refresh_token_hash",
        ),
    )
    op.create_index(
        "ix_user_sessions_user_created",
        "user_sessions",
        ["user_id", "created_at"],
    )
    op.create_index(
        "ix_user_sessions_user_active",
        "user_sessions",
        ["user_id", "revoked_at", "expires_at"],
    )
    op.create_index(
        "ix_user_sessions_family",
        "user_sessions",
        ["family_id"],
    )

    op.create_table(
        "auth_action_tokens",
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
        sa.Column("token_type", sa.Text(), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "token_type IN ('email_verification','password_reset')",
            name="ck_auth_action_tokens_type",
        ),
        sa.CheckConstraint(
            "char_length(token_hash) = 64",
            name="ck_auth_action_tokens_hash_len",
        ),
        sa.UniqueConstraint(
            "token_hash",
            name="ux_auth_action_tokens_hash",
        ),
    )
    op.create_index(
        "ix_auth_action_tokens_user_type_active",
        "auth_action_tokens",
        ["user_id", "token_type", "used_at", "expires_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_auth_action_tokens_user_type_active",
        table_name="auth_action_tokens",
    )
    op.drop_table("auth_action_tokens")

    op.drop_index(
        "ix_user_sessions_family",
        table_name="user_sessions",
    )
    op.drop_index(
        "ix_user_sessions_user_active",
        table_name="user_sessions",
    )
    op.drop_index(
        "ix_user_sessions_user_created",
        table_name="user_sessions",
    )
    op.drop_table("user_sessions")

    op.drop_index("ix_users_email_verified", table_name="users")
    op.drop_column("users", "email_verified_at")
