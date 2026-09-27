from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import ForeignKey, Index, Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPKMixin


class ManuscriptDraft(Base, UUIDPKMixin, TimestampMixin):
    """Mutable autosave buffer outside immutable manuscript history."""

    __tablename__ = "manuscript_drafts"

    report_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("reports.id", ondelete="CASCADE"),
        nullable=False,
    )
    manuscript_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("manuscripts.id", ondelete="CASCADE"),
        nullable=False,
    )
    base_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("manuscript_versions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    revision: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    content: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    __table_args__ = (
        UniqueConstraint("manuscript_id", name="ux_manuscript_drafts_manuscript"),
        Index("ix_manuscript_drafts_report", "report_id"),
        Index("ix_manuscript_drafts_updated", "updated_at"),
    )
