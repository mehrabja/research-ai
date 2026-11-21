"""Durable, report-scoped research assistant sessions (M40)."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAtMixin, TimestampMixin, UUIDPKMixin


class AgentRuntimeSession(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "agent_runtime_sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="RESTRICT"),
        nullable=False,
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="SET NULL"),
        nullable=True,
    )
    report_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("reports.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'idle'")
    )
    active_job_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="SET NULL"),
        nullable=True,
    )
    next_sequence: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    revision: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    last_message_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_error_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_event_sequence: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    next_checkpoint_sequence: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    context_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    context_summary_through_sequence: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("-1"))
    compaction_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    last_checkpoint_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "status IN ('idle','queued','running','awaiting_approval','failed','archived')",
            name="ck_agent_runtime_sessions_status",
        ),
        CheckConstraint(
            "next_sequence >= 0",
            name="ck_agent_runtime_sessions_sequence",
        ),
        CheckConstraint(
            "revision >= 0",
            name="ck_agent_runtime_sessions_revision",
        ),
        CheckConstraint("next_event_sequence >= 0", name="ck_agent_runtime_sessions_event_sequence"),
        CheckConstraint("next_checkpoint_sequence >= 0", name="ck_agent_runtime_sessions_checkpoint_sequence"),
        CheckConstraint("context_summary_through_sequence >= -1", name="ck_agent_runtime_sessions_context_sequence"),
        CheckConstraint("compaction_count >= 0", name="ck_agent_runtime_sessions_compaction_count"),
        Index(
            "ix_agent_runtime_sessions_user_updated",
            "user_id",
            "updated_at",
        ),
        Index(
            "ix_agent_runtime_sessions_report_updated",
            "report_id",
            "updated_at",
        ),
        Index(
            "ix_agent_runtime_sessions_active_job",
            "active_job_id",
            postgresql_where=text("active_job_id IS NOT NULL"),
        ),
    )


class AgentRuntimeMessage(Base, UUIDPKMixin, CreatedAtMixin):
    __tablename__ = "agent_runtime_messages"

    session_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("agent_runtime_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_refs: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    in_reply_to_message_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("agent_runtime_messages.id", ondelete="SET NULL"),
        nullable=True,
    )
    provider_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_usage: Mapped[dict[str, int | None] | None] = mapped_column(
        JSONB, nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            "role IN ('user','assistant')",
            name="ck_agent_runtime_messages_role",
        ),
        CheckConstraint(
            "sequence >= 0",
            name="ck_agent_runtime_messages_sequence",
        ),
        CheckConstraint(
            "char_length(content) BETWEEN 1 AND 20000",
            name="ck_agent_runtime_messages_content_length",
        ),
        UniqueConstraint(
            "session_id",
            "sequence",
            name="ux_agent_runtime_messages_session_sequence",
        ),
        Index(
            "ux_agent_runtime_messages_reply",
            "in_reply_to_message_id",
            unique=True,
            postgresql_where=text("in_reply_to_message_id IS NOT NULL"),
        ),
    )



class AgentRuntimeToolCall(Base, UUIDPKMixin, TimestampMixin):
    """A model-proposed operation that remains inert until user approval."""

    __tablename__ = "agent_runtime_tool_calls"

    session_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("agent_runtime_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    report_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("reports.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_message_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("agent_runtime_messages.id", ondelete="CASCADE"),
        nullable=False,
    )
    tool_key: Mapped[str] = mapped_column(Text, nullable=False)
    tool_version: Mapped[str] = mapped_column(Text, nullable=False)
    tool_description: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    arguments: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'pending'")
    )
    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    rejected_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    job_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="SET NULL"),
        nullable=True,
    )
    output_snapshot: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True
    )
    error_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    rejected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','queued','running','completed','failed','rejected')",
            name="ck_agent_runtime_tool_calls_status",
        ),
        CheckConstraint(
            "char_length(tool_key) BETWEEN 1 AND 100",
            name="ck_agent_runtime_tool_calls_key_length",
        ),
        CheckConstraint(
            "char_length(reason) BETWEEN 1 AND 500",
            name="ck_agent_runtime_tool_calls_reason_length",
        ),
        CheckConstraint(
            "jsonb_typeof(arguments) = 'object'",
            name="ck_agent_runtime_tool_calls_arguments_object",
        ),
        UniqueConstraint(
            "session_id",
            "user_message_id",
            name="ux_agent_runtime_tool_calls_turn",
        ),
        Index(
            "ix_agent_runtime_tool_calls_session_created",
            "session_id",
            "created_at",
        ),
        Index(
            "ix_agent_runtime_tool_calls_status_created",
            "status",
            "created_at",
        ),
        Index(
            "ix_agent_runtime_tool_calls_job",
            "job_id",
            postgresql_where=text("job_id IS NOT NULL"),
        ),
    )


class AgentRuntimeEvent(Base, UUIDPKMixin, CreatedAtMixin):
    """Append-only events used to replay a running turn over SSE."""

    __tablename__ = "agent_runtime_events"

    session_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("agent_runtime_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )

    __table_args__ = (
        CheckConstraint("sequence >= 1", name="ck_agent_runtime_events_sequence"),
        CheckConstraint("char_length(event_type) BETWEEN 1 AND 80", name="ck_agent_runtime_events_type_length"),
        CheckConstraint("jsonb_typeof(payload) = 'object'", name="ck_agent_runtime_events_payload_object"),
        UniqueConstraint("session_id", "sequence", name="ux_agent_runtime_events_session_sequence"),
        Index("ix_agent_runtime_events_session_sequence", "session_id", "sequence"),
    )


class AgentRuntimeCheckpoint(Base, UUIDPKMixin, CreatedAtMixin):
    """Durable session checkpoint with optional compacted conversation context."""

    __tablename__ = "agent_runtime_checkpoints"

    session_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("agent_runtime_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    checkpoint_type: Mapped[str] = mapped_column(Text, nullable=False)
    through_message_sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    context_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    state_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )

    __table_args__ = (
        CheckConstraint("sequence >= 1", name="ck_agent_runtime_checkpoints_sequence"),
        CheckConstraint("through_message_sequence >= -1", name="ck_agent_runtime_checkpoints_message_sequence"),
        CheckConstraint(
            "checkpoint_type IN ('turn_started','turn_completed','context_compaction','approval_pending','tool_approved','tool_rejected','tool_completed','turn_failed')",
            name="ck_agent_runtime_checkpoints_type",
        ),
        CheckConstraint("jsonb_typeof(state_snapshot) = 'object'", name="ck_agent_runtime_checkpoints_state_object"),
        UniqueConstraint("session_id", "sequence", name="ux_agent_runtime_checkpoints_session_sequence"),
        Index("ix_agent_runtime_checkpoints_session_created", "session_id", "created_at"),
    )
