"""M37 — Workspace membership."""
from __future__ import annotations

import uuid

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPKMixin
from app.domain.membership import MEMBERSHIP_STATUSES, ROLES


def _in_check(col: str, values: tuple[str, ...], name: str) -> CheckConstraint:
    return CheckConstraint(
        f"{col} IN (" + ",".join(f"'{v}'" for v in values) + ")",
        name=name,
    )


class WorkspaceMembership(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "workspace_memberships"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'active'"),
    )

    __table_args__ = (
        _in_check("role", ROLES, "ck_workspace_memberships_role"),
        _in_check(
            "status",
            MEMBERSHIP_STATUSES,
            "ck_workspace_memberships_status",
        ),
        UniqueConstraint(
            "workspace_id",
            "user_id",
            name="ux_workspace_memberships_ws_user",
        ),
        Index("ix_workspace_memberships_ws", "workspace_id"),
        Index("ix_workspace_memberships_user", "user_id"),
        # At most one active owner per workspace. Exactly-one is
        # enforced by the service layer + migration verification.
        Index(
            "ux_workspace_memberships_owner_active",
            "workspace_id",
            unique=True,
            postgresql_where=text(
                "role = 'owner' AND status = 'active'"
            ),
        ),
    )
