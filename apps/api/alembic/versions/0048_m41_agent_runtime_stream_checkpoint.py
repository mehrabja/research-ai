"""M41 — durable Agent Runtime events, checkpoints and context summaries."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0048"
down_revision = "0047"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("agent_runtime_sessions", sa.Column("next_event_sequence", sa.Integer(), server_default=sa.text("0"), nullable=False))
    op.add_column("agent_runtime_sessions", sa.Column("next_checkpoint_sequence", sa.Integer(), server_default=sa.text("0"), nullable=False))
    op.add_column("agent_runtime_sessions", sa.Column("context_summary", sa.Text(), nullable=True))
    op.add_column("agent_runtime_sessions", sa.Column("context_summary_through_sequence", sa.Integer(), server_default=sa.text("-1"), nullable=False))
    op.add_column("agent_runtime_sessions", sa.Column("compaction_count", sa.Integer(), server_default=sa.text("0"), nullable=False))
    op.add_column("agent_runtime_sessions", sa.Column("last_checkpoint_at", sa.DateTime(timezone=True), nullable=True))
    op.create_check_constraint("ck_agent_runtime_sessions_event_sequence", "agent_runtime_sessions", "next_event_sequence >= 0")
    op.create_check_constraint("ck_agent_runtime_sessions_checkpoint_sequence", "agent_runtime_sessions", "next_checkpoint_sequence >= 0")
    op.create_check_constraint("ck_agent_runtime_sessions_context_sequence", "agent_runtime_sessions", "context_summary_through_sequence >= -1")
    op.create_check_constraint("ck_agent_runtime_sessions_compaction_count", "agent_runtime_sessions", "compaction_count >= 0")

    op.create_table(
        "agent_runtime_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_runtime_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("sequence >= 1", name="ck_agent_runtime_events_sequence"),
        sa.CheckConstraint("char_length(event_type) BETWEEN 1 AND 80", name="ck_agent_runtime_events_type_length"),
        sa.CheckConstraint("jsonb_typeof(payload) = 'object'", name="ck_agent_runtime_events_payload_object"),
        sa.UniqueConstraint("session_id", "sequence", name="ux_agent_runtime_events_session_sequence"),
    )
    op.create_index("ix_agent_runtime_events_session_sequence", "agent_runtime_events", ["session_id", "sequence"])

    op.create_table(
        "agent_runtime_checkpoints",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_runtime_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("checkpoint_type", sa.Text(), nullable=False),
        sa.Column("through_message_sequence", sa.Integer(), nullable=False),
        sa.Column("context_summary", sa.Text(), nullable=True),
        sa.Column("state_snapshot", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("sequence >= 1", name="ck_agent_runtime_checkpoints_sequence"),
        sa.CheckConstraint("through_message_sequence >= -1", name="ck_agent_runtime_checkpoints_message_sequence"),
        sa.CheckConstraint(
            "checkpoint_type IN ('turn_started','turn_completed','context_compaction','approval_pending','tool_approved','tool_rejected','tool_completed','turn_failed')",
            name="ck_agent_runtime_checkpoints_type",
        ),
        sa.CheckConstraint("jsonb_typeof(state_snapshot) = 'object'", name="ck_agent_runtime_checkpoints_state_object"),
        sa.UniqueConstraint("session_id", "sequence", name="ux_agent_runtime_checkpoints_session_sequence"),
    )
    op.create_index("ix_agent_runtime_checkpoints_session_created", "agent_runtime_checkpoints", ["session_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_agent_runtime_checkpoints_session_created", table_name="agent_runtime_checkpoints")
    op.drop_table("agent_runtime_checkpoints")
    op.drop_index("ix_agent_runtime_events_session_sequence", table_name="agent_runtime_events")
    op.drop_table("agent_runtime_events")
    op.drop_constraint("ck_agent_runtime_sessions_compaction_count", "agent_runtime_sessions", type_="check")
    op.drop_constraint("ck_agent_runtime_sessions_context_sequence", "agent_runtime_sessions", type_="check")
    op.drop_constraint("ck_agent_runtime_sessions_checkpoint_sequence", "agent_runtime_sessions", type_="check")
    op.drop_constraint("ck_agent_runtime_sessions_event_sequence", "agent_runtime_sessions", type_="check")
    op.drop_column("agent_runtime_sessions", "last_checkpoint_at")
    op.drop_column("agent_runtime_sessions", "compaction_count")
    op.drop_column("agent_runtime_sessions", "context_summary_through_sequence")
    op.drop_column("agent_runtime_sessions", "context_summary")
    op.drop_column("agent_runtime_sessions", "next_checkpoint_sequence")
    op.drop_column("agent_runtime_sessions", "next_event_sequence")
