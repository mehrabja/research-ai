"""M42 — workspace-scoped, deployment-configured MCP connections."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0049"
down_revision = "0048"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workspace_mcp_connections",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("profile_key", sa.Text(), nullable=False),
        sa.Column(
            "created_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("status", sa.Text(), server_default=sa.text("'enabled'"), nullable=False),
        sa.Column("discovery_status", sa.Text(), server_default=sa.text("'never'"), nullable=False),
        sa.Column("protocol_version", sa.Text(), nullable=True),
        sa.Column("server_name", sa.Text(), nullable=True),
        sa.Column("server_version", sa.Text(), nullable=True),
        sa.Column("tool_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("resource_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("resource_template_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("prompt_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "capability_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("last_discovered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workspace_id",
            "profile_key",
            name="ux_workspace_mcp_connections_workspace_profile",
        ),
        sa.CheckConstraint(
            "status IN ('enabled','disabled')",
            name="ck_workspace_mcp_connections_status",
        ),
        sa.CheckConstraint(
            "discovery_status IN ('never','success','failed')",
            name="ck_workspace_mcp_connections_discovery_status",
        ),
        sa.CheckConstraint(
            "char_length(profile_key) BETWEEN 1 AND 64",
            name="ck_workspace_mcp_connections_profile_key_length",
        ),
        sa.CheckConstraint(
            "tool_count >= 0 AND resource_count >= 0 "
            "AND resource_template_count >= 0 AND prompt_count >= 0",
            name="ck_workspace_mcp_connections_counts",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(capability_snapshot) = 'object'",
            name="ck_workspace_mcp_connections_snapshot_object",
        ),
    )
    op.create_index(
        "ix_workspace_mcp_connections_workspace",
        "workspace_mcp_connections",
        ["workspace_id"],
    )
    op.create_index(
        "ix_workspace_mcp_connections_workspace_status",
        "workspace_mcp_connections",
        ["workspace_id", "status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_workspace_mcp_connections_workspace_status",
        table_name="workspace_mcp_connections",
    )
    op.drop_index(
        "ix_workspace_mcp_connections_workspace",
        table_name="workspace_mcp_connections",
    )
    op.drop_table("workspace_mcp_connections")
