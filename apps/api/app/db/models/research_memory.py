"""M26 — Research memory ORM models."""
from __future__ import annotations

import uuid

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAtMixin, TimestampMixin, UUIDPKMixin
from app.domain.retrieval_advanced import MEMORY_STATUSES, MEMORY_TYPES


def _in_check(
    col: str, values: tuple[str, ...], name: str
) -> CheckConstraint:
    return CheckConstraint(
        f"{col} IN (" + ",".join(f"'{v}'" for v in values) + ")",
        name=name,
    )


class ResearchMemory(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "research_memories"

    project_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    memory_type: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'active'")
    )

    content_fingerprint: Mapped[str] = mapped_column(
        Text, nullable=False
    )
    canonical_entity_type: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    canonical_entity_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), nullable=True
    )

    summary: Mapped[str] = mapped_column(Text, nullable=False)
    importance: Mapped[float] = mapped_column(
        Numeric, nullable=False, server_default=text("0.5")
    )
    confidence: Mapped[float] = mapped_column(
        Numeric, nullable=False, server_default=text("0.5")
    )

    source_run_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("retrieval_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    superseded_by_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("research_memories.id", ondelete="SET NULL"),
        nullable=True,
    )

    memory_meta: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True
    )
    reuse_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )

    __table_args__ = (
        _in_check(
            "memory_type", MEMORY_TYPES,
            "ck_research_memories_type",
        ),
        _in_check(
            "status", MEMORY_STATUSES,
            "ck_research_memories_status",
        ),
        CheckConstraint(
            "importance >= 0 AND importance <= 1",
            name="ck_research_memories_importance",
        ),
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_research_memories_confidence",
        ),
        CheckConstraint(
            "reuse_count >= 0",
            name="ck_research_memories_reuse_count",
        ),
        UniqueConstraint(
            "project_id", "memory_type", "content_fingerprint",
            name="ux_research_memories_project_type_fp",
        ),
        Index("ix_research_memories_project", "project_id"),
        Index(
            "ix_research_memories_project_type_status",
            "project_id", "memory_type", "status",
        ),
        Index(
            "ix_research_memories_project_entity",
            "project_id", "canonical_entity_type",
            "canonical_entity_id",
        ),
        Index("ix_research_memories_source_run", "source_run_id"),
    )


class ResearchMemoryLink(Base, UUIDPKMixin, CreatedAtMixin):
    __tablename__ = "research_memory_links"

    memory_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("research_memories.id", ondelete="CASCADE"),
        nullable=False,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    linked_entity_type: Mapped[str] = mapped_column(
        Text, nullable=False
    )
    linked_entity_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False
    )
    relation: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'references'")
    )
    weight: Mapped[float] = mapped_column(
        Numeric, nullable=False, server_default=text("1")
    )

    __table_args__ = (
        CheckConstraint(
            "weight >= 0", name="ck_research_memory_links_weight"
        ),
        UniqueConstraint(
            "memory_id", "linked_entity_type",
            "linked_entity_id", "relation",
            name="ux_research_memory_links_unique",
        ),
        Index("ix_research_memory_links_memory", "memory_id"),
        Index(
            "ix_research_memory_links_project_entity",
            "project_id", "linked_entity_type", "linked_entity_id",
        ),
    )
