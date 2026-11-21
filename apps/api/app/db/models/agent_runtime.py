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

    __table_args__ = (
        CheckConstraint(
            "status IN ('idle','queued','running','failed','archived')",
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
