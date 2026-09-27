from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAtMixin, UUIDPKMixin


class AuthSession(Base, UUIDPKMixin, CreatedAtMixin):
    """Persistent refresh session.

    The refresh credential itself is never stored. Only its SHA-256 digest
    is persisted; the opaque token is returned once to the authenticated
    client and rotated on every successful refresh.
    """

    __tablename__ = "auth_sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    token_hash: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        unique=True,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    user_agent: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    ip_address: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    __table_args__ = (
        Index(
            "ix_auth_sessions_user_active",
            "user_id",
            "expires_at",
            postgresql_where=func.coalesce(
                revoked_at,
                func.to_timestamp(0),
            ) == func.to_timestamp(0),
        ),
        Index("ix_auth_sessions_user_expires", "user_id", "expires_at"),
    )
