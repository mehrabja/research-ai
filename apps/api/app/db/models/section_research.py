"""M28 — Section Research ORM models."""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPKMixin
from app.domain.section_research import SECTION_RESEARCH_RUN_STATUSES


def _in_check(col: str, values: tuple[str, ...], name: str) -> CheckConstraint:
    return CheckConstraint(
        f"{col} IN (" + ",".join(f"'{v}'" for v in values) + ")",
        name=name,
    )


class SectionResearchRun(Base, UUIDPKMixin):
    __tablename__ = "section_research_runs"

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
    manuscript_version_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("manuscript_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    manuscript_section_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("manuscript_sections.id", ondelete="CASCADE"),
        nullable=False,
    )

    context_hash: Mapped[str] = mapped_column(Text, nullable=False)
    contract_hash: Mapped[str] = mapped_column(Text, nullable=False)
    m28_version: Mapped[str] = mapped_column(Text, nullable=False)

    status: Mapped[str] = mapped_column(Text, nullable=False)

    primary_query: Mapped[str] = mapped_column(Text, nullable=False)
    query_plan: Mapped[dict] = mapped_column(JSONB, nullable=False)
    retrieval_config: Mapped[dict] = mapped_column(JSONB, nullable=False)

    retrieval_run_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("retrieval_runs.id", ondelete="SET NULL"),
        nullable=True,
    )

    candidate_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    selected_evidence_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    coverage_score: Mapped[Decimal] = mapped_column(
        Numeric, nullable=False, server_default=text("0")
    )
    coverage_state: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'insufficient'")
    )
    coverage_summary: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True
    )

    warnings: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        _in_check(
            "status", SECTION_RESEARCH_RUN_STATUSES,
            "ck_section_research_runs_status",
        ),
        CheckConstraint(
            "candidate_count >= 0 AND selected_evidence_count >= 0",
            name="ck_section_research_runs_counts",
        ),
        CheckConstraint(
            "coverage_score >= 0 AND coverage_score <= 1",
            name="ck_section_research_runs_coverage",
        ),
        CheckConstraint(
            "duration_ms IS NULL OR duration_ms >= 0",
            name="ck_section_research_runs_duration",
        ),
        Index(
            "ix_section_research_runs_project",
            "project_id",
        ),
        Index(
            "ix_section_research_runs_section",
            "report_id", "manuscript_section_id", "created_at",
        ),
        Index(
            "ix_section_research_runs_context",
            "report_id", "manuscript_section_id", "context_hash",
        ),
        Index(
            "ux_section_research_runs_completed",
            "report_id", "manuscript_section_id", "context_hash",
            unique=True,
            postgresql_where=text("status = 'completed'"),
        ),
    )


class SectionResearchEvidence(Base, UUIDPKMixin):
    __tablename__ = "section_research_evidence"

    research_run_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("section_research_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("sources.id", ondelete="CASCADE"),
        nullable=False,
    )
    chunk_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("chunks.id", ondelete="CASCADE"),
        nullable=True,
    )

    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    final_score: Mapped[Decimal] = mapped_column(Numeric, nullable=False)

    retrieval_stage: Mapped[str] = mapped_column(Text, nullable=False)
    retrieval_reason: Mapped[list] = mapped_column(JSONB, nullable=False)

    evidence_role: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'support'")
    )
    matched_requirement_keys: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )

    citation_label: Mapped[str | None] = mapped_column(Text, nullable=True)
    excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_meta: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        CheckConstraint(
            "rank >= 1", name="ck_section_research_evidence_rank",
        ),
        CheckConstraint(
            "evidence_role IN ('primary','support')",
            name="ck_section_research_evidence_role",
        ),
        UniqueConstraint(
            "research_run_id", "rank",
            name="ux_section_research_evidence_run_rank",
        ),
        Index(
            "ix_section_research_evidence_run",
            "research_run_id", "rank",
        ),
        Index(
            "ix_section_research_evidence_project_source",
            "project_id", "source_id",
        ),
    )
