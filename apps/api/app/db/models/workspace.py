"""M37 — Workspace (tenant boundary)."""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPKMixin
from app.domain.workspace import WORKSPACE_STATUSES


def _in_check(col: str, values: tuple[str, ...], name: str) -> CheckConstraint:
    return CheckConstraint(
        f"{col} IN (" + ",".join(f"'{v}'" for v in values) + ")",
        name=name,
    )


class Workspace(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "workspaces"

    name: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(Text, nullable=False)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'active'"),
    )
    settings: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True
    )

    __table_args__ = (
        _in_check("status", WORKSPACE_STATUSES, "ck_workspaces_status"),
        CheckConstraint(
            "char_length(slug) >= 3 AND char_length(slug) <= 64",
            name="ck_workspaces_slug_length",
        ),
        Index("ux_workspaces_slug", "slug", unique=True),
        Index("ix_workspaces_owner", "owner_user_id"),
        Index("ix_workspaces_status", "status"),
    )
