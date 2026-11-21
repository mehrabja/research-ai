"""M40 — approval-gated Agent Runtime tool calls."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0047"
down_revision = "0046"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_agent_runtime_sessions_status",
        "agent_runtime_sessions",
        type_="check",
    )
    op.create_check_constraint(
        "ck_agent_runtime_sessions_status",
        "agent_runtime_sessions",
        "status IN ('idle','queued','running','awaiting_approval','failed','archived')",
    )
    op.create_table(
        "agent_runtime_tool_calls",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_runtime_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("report_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("reports.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_message_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_runtime_messages.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tool_key", sa.Text(), nullable=False),
        sa.Column("tool_version", sa.Text(), nullable=False),
        sa.Column("tool_description", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("arguments", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("approved_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("rejected_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("output_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("status IN ('pending','queued','running','completed','failed','rejected')", name="ck_agent_runtime_tool_calls_status"),
        sa.CheckConstraint("char_length(tool_key) BETWEEN 1 AND 100", name="ck_agent_runtime_tool_calls_key_length"),
        sa.CheckConstraint("char_length(reason) BETWEEN 1 AND 500", name="ck_agent_runtime_tool_calls_reason_length"),
        sa.CheckConstraint("jsonb_typeof(arguments) = 'object'", name="ck_agent_runtime_tool_calls_arguments_object"),
        sa.UniqueConstraint("session_id", "user_message_id", name="ux_agent_runtime_tool_calls_turn"),
    )
    op.create_index(
        "ix_agent_runtime_tool_calls_session_created",
        "agent_runtime_tool_calls",
        ["session_id", "created_at"],
    )
    op.create_index(
        "ix_agent_runtime_tool_calls_status_created",
        "agent_runtime_tool_calls",
        ["status", "created_at"],
    )
    op.create_index(
        "ix_agent_runtime_tool_calls_job",
        "agent_runtime_tool_calls",
        ["job_id"],
        postgresql_where=sa.text("job_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_agent_runtime_tool_calls_job", table_name="agent_runtime_tool_calls")
    op.drop_index("ix_agent_runtime_tool_calls_status_created", table_name="agent_runtime_tool_calls")
    op.drop_index("ix_agent_runtime_tool_calls_session_created", table_name="agent_runtime_tool_calls")
    op.drop_table("agent_runtime_tool_calls")
    op.drop_constraint(
        "ck_agent_runtime_sessions_status",
        "agent_runtime_sessions",
        type_="check",
    )
    op.create_check_constraint(
        "ck_agent_runtime_sessions_status",
        "agent_runtime_sessions",
        "status IN ('idle','queued','running','failed','archived')",
    )
