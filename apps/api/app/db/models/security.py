"""Security state for personal API tokens and TOTP."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPKMixin


class APIToken(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "api_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    token_prefix: Mapped[str] = mapped_column(Text, nullable=False)
    token_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    scopes: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        Index("ix_api_tokens_user_active", "user_id", "revoked_at", "expires_at"),
        Index("ix_api_tokens_prefix", "token_prefix"),
    )


class UserTwoFactor(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "user_two_factor"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    secret_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    enabled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    recovery_codes: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
    last_used_step: Mapped[int | None] = mapped_column(nullable=True)
    __table_args__ = (
        Index("ix_user_two_factor_user", "user_id"),
    )
