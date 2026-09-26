"""M30 — Citation Engine ORM models."""
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
from app.domain.citation import (
    CITATION_RELATION_TYPES,
    CITATION_RUN_STATUSES,
    CITATION_STYLES,
    CLAIM_STATUSES,
    CLAIM_TYPES,
    EVIDENCE_TYPES,
    SUPPORT_LEVELS,
)


def _in_check(col: str, values: tuple[str, ...], name: str) -> CheckConstraint:
    return CheckConstraint(
        f"{col} IN (" + ",".join(f"'{v}'" for v in values) + ")",
        name=name,
    )


class CitationRun(Base, UUIDPKMixin):
    __tablename__ = "citation_runs"

    report_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("reports.id", ondelete="CASCADE"),
        nullable=False,
    )
    manuscript_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("manuscripts.id", ondelete="SET NULL"),
        nullable=True,
    )
    manuscript_version_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("manuscript_versions.id", ondelete="RESTRICT"),
        nullable=False,
    )

    context_hash: Mapped[str] = mapped_column(Text, nullable=False)
    m30_version: Mapped[str] = mapped_column(Text, nullable=False)
    citation_style: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)

    claim_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    citation_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    unsupported_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    mixed_support_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    duplicate_reference_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    coverage_score: Mapped[Decimal] = mapped_column(
        Numeric, nullable=False, server_default=text("0")
    )

    input_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    output_summary: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
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
        _in_check("status", CITATION_RUN_STATUSES, "ck_citation_runs_status"),
        _in_check(
            "citation_style", CITATION_STYLES, "ck_citation_runs_style",
        ),
        CheckConstraint(
            "claim_count >= 0 AND citation_count >= 0 AND "
            "unsupported_count >= 0 AND mixed_support_count >= 0 AND "
            "duplicate_reference_count >= 0",
            name="ck_citation_runs_counts",
        ),
        CheckConstraint(
            "coverage_score >= 0 AND coverage_score <= 1",
            name="ck_citation_runs_coverage",
        ),
        CheckConstraint(
            "duration_ms IS NULL OR duration_ms >= 0",
            name="ck_citation_runs_duration",
        ),
        Index("ix_citation_runs_report", "report_id"),
        Index(
            "ix_citation_runs_context",
            "report_id", "manuscript_version_id",
            "context_hash", "m30_version", "citation_style",
        ),
        Index(
            "ux_citation_runs_completed",
            "report_id", "manuscript_version_id",
            "context_hash", "m30_version", "citation_style",
            unique=True,
            postgresql_where=text("status = 'completed'"),
        ),
    )


class Claim(Base, UUIDPKMixin):
    __tablename__ = "claims"

    citation_run_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("citation_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    manuscript_version_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("manuscript_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    manuscript_section_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("manuscript_sections.id", ondelete="CASCADE"),
        nullable=True,
    )
    claim_hash: Mapped[str] = mapped_column(Text, nullable=False)
    claim_text: Mapped[str] = mapped_column(Text, nullable=False)
    claim_type: Mapped[str] = mapped_column(Text, nullable=False)
    location: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    claim_meta: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'extracted'")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        _in_check("claim_type", CLAIM_TYPES, "ck_claims_type"),
        _in_check("status", CLAIM_STATUSES, "ck_claims_status"),
        UniqueConstraint(
            "citation_run_id", "claim_hash",
            name="ux_claims_run_hash",
        ),
        Index("ix_claims_run", "citation_run_id"),
        Index(
            "ix_claims_version_section",
            "manuscript_version_id", "manuscript_section_id",
        ),
    )


class ClaimEvidence(Base, UUIDPKMixin):
    __tablename__ = "claim_evidence"

    claim_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("claims.id", ondelete="CASCADE"),
        nullable=False,
    )
    evidence_type: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False,
    )
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("sources.id", ondelete="RESTRICT"),
        nullable=True,
    )
    support_level: Mapped[str] = mapped_column(Text, nullable=False)
    relevance_score: Mapped[Decimal] = mapped_column(
        Numeric, nullable=False, server_default=text("0")
    )
    provenance: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        _in_check(
            "evidence_type", EVIDENCE_TYPES, "ck_claim_evidence_type",
        ),
        _in_check(
            "support_level", SUPPORT_LEVELS, "ck_claim_evidence_support",
        ),
        CheckConstraint(
            "relevance_score >= 0 AND relevance_score <= 1",
            name="ck_claim_evidence_relevance",
        ),
        Index("ix_claim_evidence_claim", "claim_id"),
        Index(
            "ix_claim_evidence_type_id",
            "evidence_type", "evidence_id",
        ),
    )


class CitationIdentity(Base, UUIDPKMixin):
    __tablename__ = "citation_identities"

    report_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("reports.id", ondelete="CASCADE"),
        nullable=False,
    )
    identity_key: Mapped[str] = mapped_column(Text, nullable=False)

    source_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("sources.id", ondelete="RESTRICT"),
        nullable=False,
    )

    canonical_doi: Mapped[str | None] = mapped_column(Text, nullable=True)
    canonical_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    canonical_first_author: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    canonical_year: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    display_label: Mapped[str | None] = mapped_column(Text, nullable=True)
    normalization_version: Mapped[str] = mapped_column(
        Text, nullable=False,
    )
    identity_meta: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        UniqueConstraint(
            "report_id", "identity_key",
            name="ux_citation_identities_report_key",
        ),
        Index("ix_citation_identities_report", "report_id"),
        Index("ix_citation_identities_source", "source_id"),
    )


class ClaimCitation(Base, UUIDPKMixin):
    __tablename__ = "claim_citations"

    claim_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("claims.id", ondelete="CASCADE"),
        nullable=False,
    )
    citation_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("citation_identities.id", ondelete="CASCADE"),
        nullable=False,
    )
    relation_type: Mapped[str] = mapped_column(Text, nullable=False)
    support_level: Mapped[str] = mapped_column(Text, nullable=False)
    relevance_score: Mapped[Decimal] = mapped_column(
        Numeric, nullable=False, server_default=text("0")
    )

    paragraph_index: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    sentence_index: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    char_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    char_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    citation_order: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        _in_check(
            "relation_type", CITATION_RELATION_TYPES,
            "ck_claim_citations_relation",
        ),
        _in_check(
            "support_level", SUPPORT_LEVELS, "ck_claim_citations_support",
        ),
        CheckConstraint(
            "relevance_score >= 0 AND relevance_score <= 1",
            name="ck_claim_citations_relevance",
        ),
        CheckConstraint(
            "paragraph_index IS NULL OR paragraph_index >= 0",
            name="ck_claim_citations_paragraph",
        ),
        CheckConstraint(
            "sentence_index IS NULL OR sentence_index >= 0",
            name="ck_claim_citations_sentence",
        ),
        CheckConstraint(
            "char_start IS NULL OR char_end IS NULL OR char_end >= char_start",
            name="ck_claim_citations_char_range",
        ),
        CheckConstraint(
            "citation_order IS NULL OR citation_order >= 1",
            name="ck_claim_citations_order",
        ),
        UniqueConstraint(
            "claim_id", "citation_id",
            name="ux_claim_citations_pair",
        ),
        Index("ix_claim_citations_claim", "claim_id"),
        Index("ix_claim_citations_citation", "citation_id"),
        Index(
            "ix_claim_citations_placement",
            "claim_id", "paragraph_index", "sentence_index", "char_start",
        ),
    )
