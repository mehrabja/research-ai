from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAtMixin, UUIDPKMixin


class APIToken(Base, UUIDPKMixin, CreatedAtMixin):
    __tablename__ = "api_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    token_prefix: Mapped[str] = mapped_column(Text, nullable=False)
    token_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    scopes: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, server_default='["read:*"]'
    )
    allowed_workspace_ids: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, server_default='[]'
    )
    allowed_project_ids: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, server_default='[]'
    )

    __table_args__ = (
        Index("ix_api_tokens_user_active", "user_id", "revoked_at"),
        Index("ix_api_tokens_prefix", "token_prefix"),
    )
