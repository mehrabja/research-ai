"""M40 — durable report-scoped agent runtime sessions and messages."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0046"
down_revision = "0045"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_runtime_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="SET NULL"), nullable=True),
        sa.Column("report_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("reports.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'idle'"), nullable=False),
        sa.Column("active_job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("next_sequence", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("revision", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("status IN ('idle','queued','running','failed','archived')", name="ck_agent_runtime_sessions_status"),
        sa.CheckConstraint("next_sequence >= 0", name="ck_agent_runtime_sessions_sequence"),
        sa.CheckConstraint("revision >= 0", name="ck_agent_runtime_sessions_revision"),
    )
    op.create_index("ix_agent_runtime_sessions_user_updated", "agent_runtime_sessions", ["user_id", "updated_at"])
    op.create_index("ix_agent_runtime_sessions_report_updated", "agent_runtime_sessions", ["report_id", "updated_at"])
    op.create_index(
        "ix_agent_runtime_sessions_active_job",
        "agent_runtime_sessions",
        ["active_job_id"],
        postgresql_where=sa.text("active_job_id IS NOT NULL"),
    )

    op.create_table(
        "agent_runtime_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_runtime_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("evidence_refs", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("in_reply_to_message_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_runtime_messages.id", ondelete="SET NULL"), nullable=True),
        sa.Column("provider_name", sa.Text(), nullable=True),
        sa.Column("model_name", sa.Text(), nullable=True),
        sa.Column("token_usage", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("role IN ('user','assistant')", name="ck_agent_runtime_messages_role"),
        sa.CheckConstraint("sequence >= 0", name="ck_agent_runtime_messages_sequence"),
        sa.CheckConstraint("char_length(content) BETWEEN 1 AND 20000", name="ck_agent_runtime_messages_content_length"),
        sa.UniqueConstraint("session_id", "sequence", name="ux_agent_runtime_messages_session_sequence"),
    )
    op.create_index(
        "ux_agent_runtime_messages_reply",
        "agent_runtime_messages",
        ["in_reply_to_message_id"],
        unique=True,
        postgresql_where=sa.text("in_reply_to_message_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ux_agent_runtime_messages_reply", table_name="agent_runtime_messages")
    op.drop_table("agent_runtime_messages")
    op.drop_index("ix_agent_runtime_sessions_active_job", table_name="agent_runtime_sessions")
    op.drop_index("ix_agent_runtime_sessions_report_updated", table_name="agent_runtime_sessions")
    op.drop_index("ix_agent_runtime_sessions_user_updated", table_name="agent_runtime_sessions")
    op.drop_table("agent_runtime_sessions")
