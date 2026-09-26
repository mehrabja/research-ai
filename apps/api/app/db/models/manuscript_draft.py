"""M39 autosaved manuscript draft."""
from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPKMixin


class ManuscriptDraft(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "manuscript_drafts"

    manuscript_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("manuscripts.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    base_version_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("manuscript_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    sections: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    draft_hash: Mapped[str] = mapped_column(Text, nullable=False)
