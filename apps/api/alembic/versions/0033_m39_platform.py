"""M39 SaaS platform capability persistence."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0033"
down_revision = "0032"
branch_labels = None
depends_on = None


def _timestamps() -> tuple[sa.Column, sa.Column]:
    return (
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("email_verified_at", sa.DateTime(timezone=True)),
    )
    op.add_column(
        "users",
        sa.Column(
            "is_platform_admin",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )

    op.create_table(
        "auth_sessions",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        *_timestamps(),
        sa.Column(
            "user_id",
            sa.UUID(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.Text(), nullable=False, unique=True),
        sa.Column("csrf_token_hash", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("user_agent", sa.Text()),
        sa.Column("ip_hash", sa.Text()),
        sa.CheckConstraint(
            "char_length(token_hash) = 64",
            name="ck_auth_sessions_token_hash_len",
        ),
        sa.CheckConstraint(
            "char_length(csrf_token_hash) = 64",
            name="ck_auth_sessions_csrf_token_hash_len",
        ),
    )
    op.create_index(
        "ix_auth_sessions_user_active",
        "auth_sessions",
        ["user_id", "expires_at", "revoked_at"],
    )

    op.create_table(
        "oauth_accounts",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        *_timestamps(),
        sa.Column(
            "user_id",
            sa.UUID(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("provider_user_id", sa.Text(), nullable=False),
        sa.Column("provider_email", sa.Text()),
        sa.Column("metadata", sa.JSON()),
        sa.UniqueConstraint(
            "provider",
            "provider_user_id",
            name="ux_oauth_accounts_provider_user",
        ),
    )
    op.create_index("ix_oauth_accounts_user", "oauth_accounts", ["user_id"])

    op.create_table(
        "oauth_states",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("state_hash", sa.Text(), nullable=False, unique=True),
        sa.Column("redirect_uri", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "provider IN ('google', 'github')",
            name="ck_oauth_states_provider",
        ),
    )
    op.create_index(
        "ix_oauth_states_expiry",
        "oauth_states",
        ["expires_at", "used_at"],
    )

    op.create_table(
        "auth_tokens",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.UUID(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.Text(), nullable=False, unique=True),
        sa.Column("token_type", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "token_type IN ('password_reset', 'email_verification')",
            name="ck_auth_tokens_type",
        ),
    )
    op.create_index(
        "ix_auth_tokens_user_type",
        "auth_tokens",
        ["user_id", "token_type", "expires_at"],
    )

    op.create_table(
        "two_factor_auth",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        *_timestamps(),
        sa.Column(
            "user_id",
            sa.UUID(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("secret_ciphertext", sa.Text(), nullable=False),
        sa.Column(
            "enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("recovery_code_hashes", sa.JSON()),
    )

    op.create_table(
        "api_tokens",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        *_timestamps(),
        sa.Column(
            "user_id",
            sa.UUID(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.Text(), nullable=False, unique=True),
        sa.Column("token_prefix", sa.Text(), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("last_used_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
    )
    op.create_index(
        "ix_api_tokens_user_active",
        "api_tokens",
        ["user_id", "revoked_at", "expires_at"],
    )

    op.create_table(
        "notifications",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.UUID(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "workspace_id",
            sa.UUID(),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
        ),
        sa.Column("notification_type", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("data", sa.JSON()),
        sa.Column("read_at", sa.DateTime(timezone=True)),
    )
    op.create_index(
        "ix_notifications_user_created",
        "notifications",
        ["user_id", "created_at"],
    )
    op.create_index(
        "ix_notifications_user_unread",
        "notifications",
        ["user_id", "read_at", "created_at"],
    )

    op.create_table(
        "notification_preferences",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        *_timestamps(),
        sa.Column(
            "user_id",
            sa.UUID(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "email_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "job_failures",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "review_assignments",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "usage_thresholds",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "weekly_digest",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )

    op.create_table(
        "file_folders",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        *_timestamps(),
        sa.Column(
            "project_id",
            sa.UUID(),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "parent_folder_id",
            sa.UUID(),
            sa.ForeignKey("file_folders.id", ondelete="CASCADE"),
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column(
            "created_by",
            sa.UUID(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.UniqueConstraint(
            "project_id",
            "parent_folder_id",
            "name",
            name="ux_file_folders_project_parent_name",
        ),
    )
    op.create_index(
        "ix_file_folders_project_parent",
        "file_folders",
        ["project_id", "parent_folder_id"],
    )
    op.add_column(
        "project_files",
        sa.Column(
            "folder_id",
            sa.UUID(),
            sa.ForeignKey("file_folders.id", ondelete="SET NULL"),
        ),
    )

    op.create_table(
        "manuscript_drafts",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        *_timestamps(),
        sa.Column(
            "manuscript_id",
            sa.UUID(),
            sa.ForeignKey("manuscripts.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "updated_by",
            sa.UUID(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "base_version_id",
            sa.UUID(),
            sa.ForeignKey(
                "manuscript_versions.id",
                ondelete="SET NULL",
            ),
        ),
        sa.Column("sections", sa.JSON()),
        sa.Column("draft_hash", sa.Text(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("manuscript_drafts")
    op.drop_column("project_files", "folder_id")
    op.drop_index(
        "ix_file_folders_project_parent",
        table_name="file_folders",
    )
    op.drop_table("file_folders")
    op.drop_table("notification_preferences")
    op.drop_index(
        "ix_notifications_user_unread",
        table_name="notifications",
    )
    op.drop_index(
        "ix_notifications_user_created",
        table_name="notifications",
    )
    op.drop_table("notifications")
    op.drop_index(
        "ix_api_tokens_user_active",
        table_name="api_tokens",
    )
    op.drop_table("api_tokens")
    op.drop_table("two_factor_auth")
    op.drop_index(
        "ix_auth_tokens_user_type",
        table_name="auth_tokens",
    )
    op.drop_table("auth_tokens")
    op.drop_index(
        "ix_oauth_states_expiry",
        table_name="oauth_states",
    )
    op.drop_table("oauth_states")
    op.drop_index(
        "ix_oauth_accounts_user",
        table_name="oauth_accounts",
    )
    op.drop_table("oauth_accounts")
    op.drop_index(
        "ix_auth_sessions_user_active",
        table_name="auth_sessions",
    )
    op.drop_table("auth_sessions")
    op.drop_column("users", "is_platform_admin")
    op.drop_column("users", "email_verified_at")
