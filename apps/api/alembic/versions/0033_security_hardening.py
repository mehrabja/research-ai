"""Phase 12/13 — security hardening and identity controls.

Revision ID: 0033
Revises: 0032
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0033"
down_revision = "0032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("security_version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column("users", sa.Column("deletion_requested_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))

    op.add_column(
        "api_tokens",
        sa.Column("scopes", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='["read:*"]'),
    )
    op.add_column(
        "api_tokens",
        sa.Column("allowed_workspace_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
    )
    op.add_column(
        "api_tokens",
        sa.Column("allowed_project_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
    )

    op.create_table(
        "audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="SET NULL"), nullable=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="SET NULL"), nullable=True),
        sa.Column("event_code", sa.Text(), nullable=False),
        sa.Column("resource_type", sa.Text(), nullable=True),
        sa.Column("resource_id", sa.Text(), nullable=True),
        sa.Column("outcome", sa.Text(), nullable=False, server_default="success"),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("request_id", sa.Text(), nullable=True),
        sa.Column("ip_address", sa.Text(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_audit_events_actor_occurred", "audit_events", ["actor_user_id", "occurred_at"])
    op.create_index("ix_audit_events_workspace_occurred", "audit_events", ["workspace_id", "occurred_at"])
    op.create_index("ix_audit_events_project_occurred", "audit_events", ["project_id", "occurred_at"])
    op.create_index("ix_audit_events_code_occurred", "audit_events", ["event_code", "occurred_at"])

    # Existing API tokens predate scopes and remain usable, but are explicitly
    # granted read-only access until the owner rotates or recreates them.
    op.execute(sa.text("UPDATE api_tokens SET scopes = '[\\"read:*\\"]'::jsonb WHERE scopes IS NULL"))


def downgrade() -> None:
    op.drop_index("ix_audit_events_code_occurred", table_name="audit_events")
    op.drop_index("ix_audit_events_project_occurred", table_name="audit_events")
    op.drop_index("ix_audit_events_workspace_occurred", table_name="audit_events")
    op.drop_index("ix_audit_events_actor_occurred", table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_column("api_tokens", "allowed_project_ids")
    op.drop_column("api_tokens", "allowed_workspace_ids")
    op.drop_column("api_tokens", "scopes")
    op.drop_column("users", "deleted_at")
    op.drop_column("users", "deletion_requested_at")
    op.drop_column("users", "security_version")
