from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Index, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAtMixin, UUIDPKMixin


class OAuthAccount(Base, UUIDPKMixin, CreatedAtMixin):
    __tablename__ = "oauth_accounts"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    provider_user_id: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "provider",
            "provider_user_id",
            name="ux_oauth_accounts_provider_user",
        ),
        UniqueConstraint(
            "user_id",
            "provider",
            name="ux_oauth_accounts_user_provider",
        ),
        Index("ix_oauth_accounts_user", "user_id"),
    )
