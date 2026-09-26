"""M27 — Manuscript Architect ORM models."""
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
from app.domain.manuscript import (
    MANUSCRIPT_DEPENDENCY_TYPES,
    MANUSCRIPT_RUN_STATUSES,
    MANUSCRIPT_STATUSES,
    MANUSCRIPT_VERSION_STATUSES,
)


def _in_check(col: str, values: tuple[str, ...], name: str) -> CheckConstraint:
    return CheckConstraint(
        f"{col} IN (" + ",".join(f"'{v}'" for v in values) + ")",
        name=name,
    )


class Manuscript(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "manuscripts"

    report_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("reports.id", ondelete="RESTRICT"),
        nullable=False,
    )
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey(
            "manuscript_versions.id",
            ondelete="SET NULL",
            use_alter=True,
            name="fk_manuscripts_current_version",
        ),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'draft'")
    )
    architecture_version: Mapped[str] = mapped_column(Text, nullable=False)
    template_version: Mapped[str] = mapped_column(Text, nullable=False)
    context_hash: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        _in_check("status", MANUSCRIPT_STATUSES, "ck_manuscripts_status"),
        UniqueConstraint("report_id", name="ux_manuscripts_report"),
        Index("ix_manuscripts_report", "report_id"),
        Index("ix_manuscripts_status", "status"),
    )


class ManuscriptVersion(Base, UUIDPKMixin, CreatedAtMixin):
    __tablename__ = "manuscript_versions"

    manuscript_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("manuscripts.id", ondelete="CASCADE"),
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'draft'")
    )
    architecture_version: Mapped[str] = mapped_column(Text, nullable=False)
    template_version: Mapped[str] = mapped_column(Text, nullable=False)

    research_plan_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("research_plans.id", ondelete="RESTRICT"),
        nullable=False,
    )
    research_plan_version: Mapped[int] = mapped_column(
        Integer, nullable=False
    )
    research_plan_context_hash: Mapped[str] = mapped_column(
        Text, nullable=False
    )
    context_hash: Mapped[str] = mapped_column(Text, nullable=False)

    title: Mapped[str] = mapped_column(Text, nullable=False)
    title_rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    abstract_direction: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True
    )
    word_target: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )

    sections_snapshot: Mapped[list | None] = mapped_column(
        JSONB, nullable=True
    )
    architecture_meta: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True
    )

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    parent_version_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey(
            "manuscript_versions.id",
            ondelete="SET NULL",
            name="fk_manuscript_versions_parent",
        ),
        nullable=True,
    )

    __table_args__ = (
        _in_check(
            "status",
            MANUSCRIPT_VERSION_STATUSES,
            "ck_manuscript_versions_status",
        ),
        CheckConstraint("version >= 1", name="ck_manuscript_versions_version"),
        CheckConstraint(
            "word_target >= 0", name="ck_manuscript_versions_word_target"
        ),
        UniqueConstraint(
            "manuscript_id", "version",
            name="ux_manuscript_versions_ms_version",
        ),
        Index(
            "ix_manuscript_versions_ms_version",
            "manuscript_id", "version",
        ),
    )


class ManuscriptSection(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "manuscript_sections"

    manuscript_version_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("manuscript_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_research_plan_section_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("research_plan_sections.id", ondelete="SET NULL"),
        nullable=True,
    )

    section_key: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    purpose: Mapped[str | None] = mapped_column(Text, nullable=True)
    section_type: Mapped[str] = mapped_column(Text, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False)
    required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    word_budget: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    budget_weight: Mapped[Decimal] = mapped_column(
        Numeric, nullable=False, server_default=text("0")
    )
    evidence_coverage_target: Mapped[Decimal] = mapped_column(
        Numeric, nullable=False, server_default=text("0")
    )
    research_objective: Mapped[str | None] = mapped_column(Text, nullable=True)
    writing_objective: Mapped[str | None] = mapped_column(Text, nullable=True)
    citation_required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    research_contract: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    section_meta: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'active'")
    )

    __table_args__ = (
        UniqueConstraint(
            "manuscript_version_id", "section_key",
            name="ux_manuscript_sections_key",
        ),
        UniqueConstraint(
            "manuscript_version_id", "display_order",
            name="ux_manuscript_sections_order",
        ),
        CheckConstraint(
            "display_order >= 0", name="ck_manuscript_sections_order"
        ),
        CheckConstraint(
            "word_budget >= 0", name="ck_manuscript_sections_wb"
        ),
        CheckConstraint(
            "budget_weight >= 0", name="ck_manuscript_sections_bw"
        ),
        CheckConstraint(
            "evidence_coverage_target >= 0 AND "
            "evidence_coverage_target <= 1",
            name="ck_manuscript_sections_ect",
        ),
        Index(
            "ix_manuscript_sections_version_order",
            "manuscript_version_id", "display_order",
        ),
    )


class ManuscriptSectionDependency(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "manuscript_section_dependencies"

    manuscript_version_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("manuscript_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    upstream_section_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("manuscript_sections.id", ondelete="CASCADE"),
        nullable=False,
    )
    downstream_section_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("manuscript_sections.id", ondelete="CASCADE"),
        nullable=False,
    )
    dependency_type: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'requires'")
    )
    dependency_meta: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True
    )

    __table_args__ = (
        _in_check(
            "dependency_type",
            MANUSCRIPT_DEPENDENCY_TYPES,
            "ck_manuscript_section_dependencies_type",
        ),
        UniqueConstraint(
            "manuscript_version_id",
            "upstream_section_id",
            "downstream_section_id",
            name="ux_manuscript_section_dependencies_edge",
        ),
        CheckConstraint(
            "upstream_section_id <> downstream_section_id",
            name="ck_manuscript_section_dependencies_no_self",
        ),
        Index(
            "ix_manuscript_section_dependencies_version",
            "manuscript_version_id",
        ),
    )


class ManuscriptRun(Base):
    __tablename__ = "manuscript_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
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
    manuscript_version_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("manuscript_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    context_hash: Mapped[str] = mapped_column(Text, nullable=False)
    architecture_version: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
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
        _in_check(
            "status", MANUSCRIPT_RUN_STATUSES, "ck_manuscript_runs_status"
        ),
        CheckConstraint(
            "duration_ms IS NULL OR duration_ms >= 0",
            name="ck_manuscript_runs_duration",
        ),
        Index("ix_manuscript_runs_report", "report_id"),
        Index(
            "ix_manuscript_runs_context",
            "report_id", "context_hash",
        ),
        Index(
            "ux_manuscript_runs_completed",
            "report_id", "context_hash", "architecture_version",
            unique=True,
            postgresql_where=text("status = 'completed'"),
        ),
    )
