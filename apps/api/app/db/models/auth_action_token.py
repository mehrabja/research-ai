"""One-time email verification and password reset token records."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAtMixin, UUIDPKMixin


class AuthActionToken(Base, UUIDPKMixin, CreatedAtMixin):
    __tablename__ = "auth_action_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    token_type: Mapped[str] = mapped_column(Text, nullable=False)
    token_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            "token_type IN ('email_verification','password_reset')",
            name="ck_auth_action_tokens_type",
        ),
        CheckConstraint(
            "char_length(token_hash) = 64",
            name="ck_auth_action_tokens_hash_len",
        ),
        Index(
            "ix_auth_action_tokens_user_type_active",
            "user_id",
            "token_type",
            "used_at",
            "expires_at",
        ),
    )
