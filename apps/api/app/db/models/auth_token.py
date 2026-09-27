from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAtMixin, UUIDPKMixin


class AuthOneTimeToken(Base, UUIDPKMixin, CreatedAtMixin):
    """Single-use verification/reset credential.

    Only a SHA-256 digest is stored. The raw token exists only in the
    URL/email delivered to the user.
    """

    __tablename__ = "auth_one_time_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    purpose: Mapped[str] = mapped_column(
        Text,
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
    consumed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    __table_args__ = (
        Index(
            "ix_auth_one_time_tokens_user_purpose",
            "user_id",
            "purpose",
            "expires_at",
        ),
        Index(
            "ix_auth_one_time_tokens_active",
            "purpose",
            "expires_at",
            postgresql_where="consumed_at IS NULL",
        ),
    )
