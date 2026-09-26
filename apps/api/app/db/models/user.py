from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPKMixin


class User(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(Text, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    full_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    email_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_platform_admin: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )

    __table_args__ = (
        # Case-insensitive uniqueness without citext.
        Index("ux_users_email_lower", text("lower(email)"), unique=True),
    )
