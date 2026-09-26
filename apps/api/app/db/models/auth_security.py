"""M39 persistent authentication security models."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAtMixin, TimestampMixin, UUIDPKMixin


class AuthSession(Base, UUIDPKMixin, CreatedAtMixin, TimestampMixin):
    __tablename__ = "auth_sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    token_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    csrf_token_hash: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip_hash: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index(
            "ix_auth_sessions_user_active",
            "user_id",
            "expires_at",
            "revoked_at",
        ),
        CheckConstraint(
            "char_length(token_hash) = 64",
            name="ck_auth_sessions_token_hash_len",
        ),
        CheckConstraint(
            "char_length(csrf_token_hash) = 64",
            name="ck_auth_sessions_csrf_hash_len",
        ),
    )


class OAuthAccount(Base, UUIDPKMixin, CreatedAtMixin, TimestampMixin):
    __tablename__ = "oauth_accounts"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    provider_user_id: Mapped[str] = mapped_column(Text, nullable=False)
    provider_email: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider_metadata: Mapped[dict | None] = mapped_column(
        "metadata",
        JSONB,
        nullable=True,
    )

    __table_args__ = (
        UniqueConstraint(
            "provider",
            "provider_user_id",
            name="ux_oauth_accounts_provider_user",
        ),
        Index("ix_oauth_accounts_user", "user_id"),
    )


class OAuthState(Base, UUIDPKMixin, CreatedAtMixin):
    __tablename__ = "oauth_states"

    provider: Mapped[str] = mapped_column(Text, nullable=False)
    state_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    redirect_uri: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    __table_args__ = (
        CheckConstraint(
            "provider IN ('google', 'github')",
            name="ck_oauth_states_provider",
        ),
        Index("ix_oauth_states_expiry", "expires_at", "used_at"),
    )


class AuthToken(Base, UUIDPKMixin, CreatedAtMixin):
    __tablename__ = "auth_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    token_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    token_type: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    __table_args__ = (
        CheckConstraint(
            "token_type IN ('password_reset', 'email_verification')",
            name="ck_auth_tokens_type",
        ),
        Index(
            "ix_auth_tokens_user_type",
            "user_id",
            "token_type",
            "expires_at",
        ),
    )


class TwoFactorAuth(Base, UUIDPKMixin, CreatedAtMixin, TimestampMixin):
    __tablename__ = "two_factor_auth"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    secret_ciphertext: Mapped[str] = mapped_column(Text, nullable=False)
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
    )
    recovery_code_hashes: Mapped[list[str] | None] = mapped_column(
        JSONB,
        nullable=True,
    )
