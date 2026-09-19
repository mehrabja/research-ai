"""M21 — Taxonomy ORM models."""
from __future__ import annotations

import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPKMixin


class ResearchDomain(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "research_domains"

    code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("research_domains.id", ondelete="SET NULL"),
        nullable=True,
    )
    depth: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    aliases: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    taxonomy_version: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "depth >= 0 AND depth <= 3",
            name="ck_research_domains_depth",
        ),
        Index("ix_research_domains_parent", "parent_id"),
        Index("ix_research_domains_active", "is_active"),
    )


class PaperType(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "paper_types"

    code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    aliases: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    default_design_code: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey(
            "research_designs.code",
            ondelete="SET NULL",
            name="fk_paper_types_default_design_code",
        ),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    taxonomy_version: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        Index("ix_paper_types_active", "is_active"),
    )


class ResearchDesign(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "research_designs"

    code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    aliases: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    taxonomy_version: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        Index("ix_research_designs_active", "is_active"),
    )
