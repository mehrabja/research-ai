"""M23 — Literature intelligence ORM models."""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
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

from app.db.base import Base, CreatedAtMixin, TimestampMixin, UUIDPKMixin
from app.domain.literature import (
    ANALYSIS_STATUSES,
    CLUSTER_STATUSES,
    GAP_STATUSES,
    GAP_TYPES,
    RUN_STATUSES,
    SCREENING_STATUSES,
)


def _in_check(
    column: str,
    values: tuple[str, ...],
    name: str,
) -> CheckConstraint:
    return CheckConstraint(
        f"{column} IN (" + ",".join(f"'{v}'" for v in values) + ")",
        name=name,
    )


class ProjectLiteratureItem(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "project_literature_items"

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

    screening_status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'discovered'"),
    )
    manual_override: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
    )
    manual_override_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    manual_override_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    manual_override_reason: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )

    relevance_score: Mapped[Decimal | None] = mapped_column(
        Numeric, nullable=True
    )
    relevance_confidence: Mapped[Decimal | None] = mapped_column(
        Numeric, nullable=True
    )
    relevance_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    relevance_factors: Mapped[list | None] = mapped_column(
        JSONB, nullable=True
    )

    paper_type_code: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey(
            "paper_types.code",
            ondelete="SET NULL",
            name="fk_project_literature_items_paper_type",
        ),
        nullable=True,
    )
    research_design_code: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey(
            "research_designs.code",
            ondelete="SET NULL",
            name="fk_project_literature_items_design_code",
        ),
        nullable=True,
    )

    study_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    methods_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    findings_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    limitations_summary: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )

    population: Mapped[str | None] = mapped_column(Text, nullable=True)
    sample_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    intervention: Mapped[str | None] = mapped_column(Text, nullable=True)
    comparator: Mapped[str | None] = mapped_column(Text, nullable=True)
    outcomes: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    themes: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    keywords: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    item_meta: Mapped[dict | None] = mapped_column(
        "metadata", JSONB, nullable=True
    )

    extraction_provenance: Mapped[list | None] = mapped_column(
        JSONB, nullable=True
    )

    analysis_status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'pending'"),
    )
    analysis_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    analysis_version: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )

    __table_args__ = (
        UniqueConstraint(
            "project_id", "source_id",
            name="ux_project_literature_items_project_source",
        ),
        _in_check(
            "screening_status",
            SCREENING_STATUSES,
            "ck_project_literature_items_screening",
        ),
        _in_check(
            "analysis_status",
            ANALYSIS_STATUSES,
            "ck_project_literature_items_analysis",
        ),
        CheckConstraint(
            "relevance_score IS NULL OR "
            "(relevance_score >= 0 AND relevance_score <= 1)",
            name="ck_project_literature_items_relevance_range",
        ),
        CheckConstraint(
            "relevance_confidence IS NULL OR "
            "(relevance_confidence >= 0 AND relevance_confidence <= 1)",
            name="ck_project_literature_items_conf_range",
        ),
        CheckConstraint(
            "sample_size IS NULL OR sample_size >= 0",
            name="ck_project_literature_items_sample_size",
        ),
        Index(
            "ix_project_literature_items_project_status",
            "project_id",
            "screening_status",
        ),
        Index(
            "ix_project_literature_items_project_analysis",
            "project_id",
            "analysis_status",
        ),
        Index(
            "ix_project_literature_items_source",
            "source_id",
        ),
    )


class LiteratureCluster(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "literature_clusters"

    project_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )

    name: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    cluster_method: Mapped[str] = mapped_column(Text, nullable=False)
    cluster_version: Mapped[str] = mapped_column(Text, nullable=False)

    source_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )

    themes: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    keywords: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    disagreements: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    limitations: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    representative_source_ids: Mapped[list | None] = mapped_column(
        JSONB, nullable=True
    )
    evidence_strength: Mapped[Decimal | None] = mapped_column(
        Numeric, nullable=True
    )
    cluster_meta: Mapped[dict | None] = mapped_column(
        "metadata", JSONB, nullable=True
    )

    status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'pending'"),
    )

    __table_args__ = (
        _in_check(
            "status",
            CLUSTER_STATUSES,
            "ck_literature_clusters_status",
        ),
        CheckConstraint(
            "source_count >= 0",
            name="ck_literature_clusters_source_count",
        ),
        CheckConstraint(
            "evidence_strength IS NULL OR "
            "(evidence_strength >= 0 AND evidence_strength <= 1)",
            name="ck_literature_clusters_evidence_range",
        ),
        Index(
            "ix_literature_clusters_project_status",
            "project_id",
            "status",
        ),
    )


class LiteratureClusterMember(Base, UUIDPKMixin, CreatedAtMixin):
    __tablename__ = "literature_cluster_members"

    cluster_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("literature_clusters.id", ondelete="CASCADE"),
        nullable=False,
    )
    literature_item_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("project_literature_items.id", ondelete="CASCADE"),
        nullable=False,
    )

    similarity_score: Mapped[Decimal | None] = mapped_column(
        Numeric, nullable=True
    )
    membership_reason: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )

    __table_args__ = (
        UniqueConstraint(
            "cluster_id", "literature_item_id",
            name="ux_literature_cluster_members_cluster_item",
        ),
        CheckConstraint(
            "similarity_score IS NULL OR "
            "(similarity_score >= -1 AND similarity_score <= 1)",
            name="ck_literature_cluster_members_similarity",
        ),
        Index(
            "ix_literature_cluster_members_item",
            "literature_item_id",
        ),
    )


class LiteratureGap(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "literature_gaps"

    project_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )

    gap_type: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    confidence: Mapped[Decimal] = mapped_column(Numeric, nullable=False)

    supporting_source_ids: Mapped[list | None] = mapped_column(
        JSONB, nullable=True
    )
    supporting_cluster_ids: Mapped[list | None] = mapped_column(
        JSONB, nullable=True
    )
    evidence_summary: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )

    status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'candidate'"),
    )

    analysis_version: Mapped[str] = mapped_column(
        Text, nullable=False
    )

    fingerprint: Mapped[str | None] = mapped_column(Text, nullable=True)

    gap_meta: Mapped[dict | None] = mapped_column(
        "metadata", JSONB, nullable=True
    )

    __table_args__ = (
        _in_check(
            "gap_type",
            GAP_TYPES,
            "ck_literature_gaps_type",
        ),
        _in_check(
            "status",
            GAP_STATUSES,
            "ck_literature_gaps_status",
        ),
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_literature_gaps_confidence_range",
        ),
        Index(
            "ix_literature_gaps_project_status",
            "project_id",
            "status",
        ),
        Index(
            "ix_literature_gaps_project_type",
            "project_id",
            "gap_type",
        ),
        Index(
            "ux_literature_gaps_project_fingerprint",
            "project_id",
            "fingerprint",
            unique=True,
            postgresql_where=text("fingerprint IS NOT NULL"),
        ),
    )


class LiteratureIntelligenceRun(Base):
    __tablename__ = "literature_intelligence_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )

    context_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    analysis_version: Mapped[str] = mapped_column(
        Text, nullable=False
    )

    status: Mapped[str] = mapped_column(Text, nullable=False)

    source_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    included_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    excluded_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    cluster_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    gap_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )

    duration_ms: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    error_message: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        _in_check(
            "status",
            RUN_STATUSES,
            "ck_literature_intelligence_runs_status",
        ),
        CheckConstraint(
            "source_count >= 0 AND included_count >= 0 "
            "AND excluded_count >= 0 AND cluster_count >= 0 "
            "AND gap_count >= 0",
            name="ck_literature_intelligence_runs_counts",
        ),
        CheckConstraint(
            "duration_ms IS NULL OR duration_ms >= 0",
            name="ck_literature_intelligence_runs_duration",
        ),
        Index(
            "ix_literature_intelligence_runs_project_created",
            "project_id",
            "created_at",
        ),
        Index(
            "ix_literature_intelligence_runs_context_hash",
            "project_id",
            "context_hash",
        ),
        Index(
            "ux_lit_runs_unique_completed",
            "project_id",
            "context_hash",
            "analysis_version",
            unique=True,
            postgresql_where=text("status = 'completed'"),
        ),
    )
