"""M37 — Workspace invitations (hash-only storage)."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAtMixin, UUIDPKMixin
from app.domain.membership import ROLES


def _in_check(col: str, values: tuple[str, ...], name: str) -> CheckConstraint:
    return CheckConstraint(
        f"{col} IN (" + ",".join(f"'{v}'" for v in values) + ")",
        name=name,
    )


class WorkspaceInvitation(Base, UUIDPKMixin, CreatedAtMixin):
    __tablename__ = "workspace_invitations"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    email: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    # sha256(raw_token).hexdigest() — never the raw token.
    token_hash: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    invited_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    __table_args__ = (
        _in_check("role", ROLES, "ck_workspace_invitations_role"),
        CheckConstraint(
            "char_length(email) > 0",
            name="ck_workspace_invitations_email",
        ),
        CheckConstraint(
            "char_length(token_hash) = 64",
            name="ck_workspace_invitations_token_hash_len",
        ),
        Index(
            "ux_workspace_invitations_token_hash",
            "token_hash",
            unique=True,
        ),
        Index(
            "ix_workspace_invitations_ws_status",
            "workspace_id",
            "accepted_at",
            "revoked_at",
        ),
        Index(
            "ix_workspace_invitations_email",
            text("lower(email)"),
        ),
    )
