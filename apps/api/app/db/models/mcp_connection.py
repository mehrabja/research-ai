"""Workspace-scoped registrations for deployment-configured MCP servers."""
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

from app.db.base import Base, TimestampMixin, UUIDPKMixin


class WorkspaceMCPConnection(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "workspace_mcp_connections"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    profile_key: Mapped[str] = mapped_column(Text, nullable=False)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'enabled'"),
    )
    discovery_status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'never'"),
    )
    protocol_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    server_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    server_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    tool_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    resource_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    resource_template_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    prompt_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    capability_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    last_discovered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_error_code: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "status IN ('enabled','disabled')",
            name="ck_workspace_mcp_connections_status",
        ),
        CheckConstraint(
            "discovery_status IN ('never','success','failed')",
            name="ck_workspace_mcp_connections_discovery_status",
        ),
        CheckConstraint(
            "char_length(profile_key) BETWEEN 1 AND 64",
            name="ck_workspace_mcp_connections_profile_key_length",
        ),
        CheckConstraint(
            "tool_count >= 0 AND resource_count >= 0 "
            "AND resource_template_count >= 0 AND prompt_count >= 0",
            name="ck_workspace_mcp_connections_counts",
        ),
        CheckConstraint(
            "jsonb_typeof(capability_snapshot) = 'object'",
            name="ck_workspace_mcp_connections_snapshot_object",
        ),
        UniqueConstraint(
            "workspace_id",
            "profile_key",
            name="ux_workspace_mcp_connections_workspace_profile",
        ),
        Index("ix_workspace_mcp_connections_workspace", "workspace_id"),
        Index(
            "ix_workspace_mcp_connections_workspace_status",
            "workspace_id",
            "status",
        ),
    )
