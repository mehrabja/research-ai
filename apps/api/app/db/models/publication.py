"""M33 — Publication target + compliance ORM models."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAtMixin, TimestampMixin, UUIDPKMixin
from app.domain.publication import (
    CITATION_STYLES,
    COMPLIANCE_CATEGORIES,
    COMPLIANCE_GATES,
    COMPLIANCE_SEVERITIES,
    COMPLIANCE_STATUSES,
    TARGET_VENUE_TYPES,
)


def _in_check(col: str, values: tuple[str, ...], name: str) -> CheckConstraint:
    return CheckConstraint(
        f"{col} IN (" + ",".join(f"'{v}'" for v in values) + ")",
        name=name,
    )


class PublicationTarget(Base, UUIDPKMixin, TimestampMixin):
    """A specific version of a venue's rules.

    Each row = (target_code, profile_version). Immutable once created;
    to change rules, create a new row with an incremented profile_version
    and set ``active=False`` on the prior row.
    """

    __tablename__ = "publication_targets"

    target_code: Mapped[str] = mapped_column(Text, nullable=False)
    profile_version: Mapped[str] = mapped_column(Text, nullable=False)

    publisher: Mapped[str | None] = mapped_column(Text, nullable=True)
    venue: Mapped[str] = mapped_column(Text, nullable=False)
    venue_type: Mapped[str] = mapped_column(Text, nullable=False)

    citation_style: Mapped[str] = mapped_column(Text, nullable=False)

    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )

    paper_types: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    formatting_rules: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True
    )
    section_rules: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True
    )
    word_limits: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    abstract_limits: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True
    )
    keyword_rules: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True
    )
    author_rules: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True
    )
    anonymity_rules: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True
    )
    figure_table_rules: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True
    )
    supplementary_rules: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True
    )
    reference_rules: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True
    )
    submission_checklist: Mapped[list | None] = mapped_column(
        JSONB, nullable=True
    )

    profile_schema_version: Mapped[str] = mapped_column(
        Text, nullable=False
    )
    provenance: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    effective_from: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    effective_to: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        _in_check(
            "venue_type", TARGET_VENUE_TYPES,
            "ck_publication_targets_venue_type",
        ),
        _in_check(
            "citation_style", CITATION_STYLES,
            "ck_publication_targets_citation_style",
        ),
        UniqueConstraint(
            "target_code", "profile_version",
            name="ux_publication_targets_code_version",
        ),
        Index(
            "ix_publication_targets_code_active",
            "target_code", "active",
        ),
        Index("ix_publication_targets_venue", "venue"),
    )


class PublicationTargetSelection(Base, UUIDPKMixin, CreatedAtMixin):
    """Which target version is bound to a report."""

    __tablename__ = "publication_target_selections"

    report_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("reports.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("publication_targets.id", ondelete="RESTRICT"),
        nullable=False,
    )
    selected_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    selection_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index(
            "ix_publication_target_selections_report",
            "report_id",
        ),
    )


class PublicationComplianceRun(Base, UUIDPKMixin):
    __tablename__ = "publication_compliance_runs"

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
    target_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("publication_targets.id", ondelete="RESTRICT"),
        nullable=False,
    )

    context_hash: Mapped[str] = mapped_column(Text, nullable=False)
    m33_version: Mapped[str] = mapped_column(Text, nullable=False)
    rules_version: Mapped[str] = mapped_column(Text, nullable=False)
    target_profile_version: Mapped[str] = mapped_column(
        Text, nullable=False
    )
    status: Mapped[str] = mapped_column(Text, nullable=False)

    finding_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    blocking_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    error_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    warning_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    info_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )

    gate: Mapped[str | None] = mapped_column(Text, nullable=True)
    checklist_state: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True
    )
    formatting_summary: Mapped[dict | None] = mapped_column(
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
            "status", COMPLIANCE_STATUSES,
            "ck_publication_compliance_runs_status",
        ),
        CheckConstraint(
            "gate IS NULL OR gate IN (" +
            ",".join(f"'{v}'" for v in COMPLIANCE_GATES) + ")",
            name="ck_publication_compliance_runs_gate",
        ),
        CheckConstraint(
            "finding_count >= 0 AND blocking_count >= 0 AND "
            "error_count >= 0 AND warning_count >= 0 AND info_count >= 0",
            name="ck_publication_compliance_runs_counts",
        ),
        CheckConstraint(
            "duration_ms IS NULL OR duration_ms >= 0",
            name="ck_publication_compliance_runs_duration",
        ),
        Index(
            "ix_publication_compliance_runs_project",
            "project_id",
        ),
        Index(
            "ix_publication_compliance_runs_report",
            "report_id",
        ),
        Index(
            "ix_publication_compliance_runs_context",
            "report_id", "manuscript_version_id",
            "target_id", "context_hash",
            "m33_version", "rules_version",
        ),
        Index(
            "ux_publication_compliance_runs_completed",
            "report_id", "manuscript_version_id",
            "target_id", "context_hash",
            "m33_version", "rules_version",
            unique=True,
            postgresql_where=text("status = 'completed'"),
        ),
    )


class PublicationComplianceFinding(Base, UUIDPKMixin):
    __tablename__ = "publication_compliance_findings"

    compliance_run_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey(
            "publication_compliance_runs.id", ondelete="CASCADE",
        ),
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

    rule_id: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)

    location: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    evidence: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    remediation: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True
    )
    finding_meta: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        _in_check(
            "category", COMPLIANCE_CATEGORIES,
            "ck_publication_compliance_findings_category",
        ),
        _in_check(
            "severity", COMPLIANCE_SEVERITIES,
            "ck_publication_compliance_findings_severity",
        ),
        Index(
            "ix_publication_compliance_findings_run",
            "compliance_run_id",
        ),
        Index(
            "ix_publication_compliance_findings_run_severity",
            "compliance_run_id", "severity",
        ),
    )
