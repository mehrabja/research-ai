from __future__ import annotations

import uuid

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPKMixin


class ResearchCanvas(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "research_canvases"

    project_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    revision: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="1"
    )
    nodes: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
    edges: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
    viewport: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default='{"x":0,"y":0,"zoom":1}',
    )
    updated_by_user: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
    )

    __table_args__ = (
        CheckConstraint(
            "revision >= 1",
            name="ck_research_canvases_revision_pos",
        ),
        Index(
            "ix_research_canvases_project",
            "project_id",
        ),
    )
