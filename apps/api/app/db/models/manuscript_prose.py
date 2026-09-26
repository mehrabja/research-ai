"""M28.5 — Manuscript prose generation ORM models."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
)
from sqlalchemy import text as sa_text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAtMixin, UUIDPKMixin
from app.domain.manuscript_prose import (
    PROSE_GENERATION_MODES,
    PROSE_RUN_STATUSES,
    PROSE_SECTION_STATUSES,
)


def _in_check(col: str, values: tuple[str, ...], name: str) -> CheckConstraint:
    return CheckConstraint(
        f"{col} IN (" + ",".join(f"'{v}'" for v in values) + ")",
        name=name,
    )


class ManuscriptProseRun(Base, UUIDPKMixin, CreatedAtMixin):
    __tablename__ = "manuscript_prose_runs"

    project_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    report_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("reports.id", ondelete="CASCADE"),
        nullable=False,
    )
    manuscript_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("manuscripts.id", ondelete="CASCADE"),
        nullable=False,
    )
    base_manuscript_version_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("manuscript_versions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    output_manuscript_version_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("manuscript_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    research_plan_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("research_plans.id", ondelete="SET NULL"),
        nullable=True,
    )
    section_research_run_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("section_research_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    technical_intelligence_run_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey(
            "technical_intelligence_runs.id", ondelete="SET NULL",
        ),
        nullable=True,
    )
    citation_run_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("citation_runs.id", ondelete="SET NULL"),
        nullable=True,
    )

    context_hash: Mapped[str] = mapped_column(Text, nullable=False)
    prose_version: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_version: Mapped[str] = mapped_column(Text, nullable=False)
    generation_mode: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str | None] = mapped_column(Text, nullable=True)
    model: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[str] = mapped_column(Text, nullable=False)

    section_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=sa_text("0")
    )
    paragraph_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=sa_text("0")
    )
    sentence_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=sa_text("0")
    )
    word_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=sa_text("0")
    )

    warnings: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    errors: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    input_snapshot: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True
    )
    output_summary: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        _in_check("status", PROSE_RUN_STATUSES,
                  "ck_manuscript_prose_runs_status"),
        _in_check("generation_mode", PROSE_GENERATION_MODES,
                  "ck_manuscript_prose_runs_mode"),
        CheckConstraint(
            "section_count >= 0 AND paragraph_count >= 0 AND "
            "sentence_count >= 0 AND word_count >= 0",
            name="ck_manuscript_prose_runs_counts",
        ),
        CheckConstraint(
            "duration_ms IS NULL OR duration_ms >= 0",
            name="ck_manuscript_prose_runs_duration",
        ),
        Index("ix_manuscript_prose_runs_project", "project_id"),
        Index("ix_manuscript_prose_runs_report", "report_id"),
        Index(
            "ix_manuscript_prose_runs_context",
            "report_id", "base_manuscript_version_id",
            "context_hash", "prose_version",
        ),
        Index(
            "ux_manuscript_prose_runs_completed",
            "report_id", "base_manuscript_version_id",
            "context_hash", "prose_version",
            unique=True,
            postgresql_where=sa_text("status = 'completed'"),
        ),
    )


class ManuscriptProseSection(Base, UUIDPKMixin, CreatedAtMixin):
    __tablename__ = "manuscript_prose_sections"

    run_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("manuscript_prose_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    report_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("reports.id", ondelete="CASCADE"),
        nullable=False,
    )
    manuscript_version_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("manuscript_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    manuscript_section_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("manuscript_sections.id", ondelete="SET NULL"),
        nullable=True,
    )

    section_key: Mapped[str] = mapped_column(Text, nullable=False)
    section_type: Mapped[str] = mapped_column(Text, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)

    text: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=sa_text("''")
    )
    char_start: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=sa_text("0")
    )
    char_end: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=sa_text("0")
    )
    word_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=sa_text("0")
    )
    paragraph_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=sa_text("0")
    )
    sentence_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=sa_text("0")
    )

    section_context_hash: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=sa_text("''")
    )
    provenance: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True
    )
    warnings: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        _in_check("status", PROSE_SECTION_STATUSES,
                  "ck_manuscript_prose_sections_status"),
        CheckConstraint(
            "word_count >= 0 AND paragraph_count >= 0 AND "
            "sentence_count >= 0",
            name="ck_manuscript_prose_sections_counts",
        ),
        UniqueConstraint(
            "run_id", "section_key",
            name="ux_manuscript_prose_sections_run_key",
        ),
        Index(
            "ix_manuscript_prose_sections_run_order",
            "run_id", "display_order",
        ),
        Index(
            "ix_manuscript_prose_sections_version",
            "manuscript_version_id",
        ),
    )


class ManuscriptProseParagraph(Base, UUIDPKMixin, CreatedAtMixin):
    __tablename__ = "manuscript_prose_paragraphs"

    section_row_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("manuscript_prose_sections.id", ondelete="CASCADE"),
        nullable=False,
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("manuscript_prose_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )

    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    char_start: Mapped[int] = mapped_column(Integer, nullable=False)
    char_end: Mapped[int] = mapped_column(Integer, nullable=False)
    sentence_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=sa_text("0")
    )
    paragraph_hash: Mapped[str] = mapped_column(Text, nullable=False)
    provenance: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            "ordinal >= 0 AND sentence_count >= 0 AND "
            "char_start >= 0 AND char_end >= char_start",
            name="ck_manuscript_prose_paragraphs_shape",
        ),
        UniqueConstraint(
            "section_row_id", "ordinal",
            name="ux_manuscript_prose_paragraphs_ordinal",
        ),
        Index(
            "ix_manuscript_prose_paragraphs_section",
            "section_row_id", "ordinal",
        ),
    )


class ManuscriptProseSentence(Base, UUIDPKMixin, CreatedAtMixin):
    __tablename__ = "manuscript_prose_sentences"

    paragraph_row_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("manuscript_prose_paragraphs.id", ondelete="CASCADE"),
        nullable=False,
    )
    section_row_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("manuscript_prose_sections.id", ondelete="CASCADE"),
        nullable=False,
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("manuscript_prose_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )

    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    global_ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    char_start: Mapped[int] = mapped_column(Integer, nullable=False)
    char_end: Mapped[int] = mapped_column(Integer, nullable=False)
    sentence_hash: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_refs: Mapped[list | None] = mapped_column(
        JSONB, nullable=True
    )
    citation_refs: Mapped[list | None] = mapped_column(
        JSONB, nullable=True
    )
    provenance: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            "ordinal >= 0 AND global_ordinal >= 0 AND "
            "char_start >= 0 AND char_end >= char_start",
            name="ck_manuscript_prose_sentences_shape",
        ),
        UniqueConstraint(
            "section_row_id", "global_ordinal",
            name="ux_manuscript_prose_sentences_global_order",
        ),
        Index(
            "ix_manuscript_prose_sentences_paragraph",
            "paragraph_row_id", "ordinal",
        ),
    )
