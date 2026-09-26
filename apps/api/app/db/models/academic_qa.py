"""M31 — Academic QA ORM models."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPKMixin
from app.domain.academic_qa import (
    QA_CATEGORIES,
    QA_CLASSIFICATIONS,
    QA_EXECUTION_MODES,
    QA_FINDING_STATUSES,
    QA_GATES,
    QA_SEVERITIES,
    QA_STATUSES,
)


def _in_check(col: str, values: tuple[str, ...], name: str) -> CheckConstraint:
    return CheckConstraint(
        f"{col} IN (" + ",".join(f"'{v}'" for v in values) + ")",
        name=name,
    )


class AcademicQARun(Base, UUIDPKMixin):
    __tablename__ = "academic_qa_runs"

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

    context_hash: Mapped[str] = mapped_column(Text, nullable=False)
    m31_version: Mapped[str] = mapped_column(Text, nullable=False)
    rules_version: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    execution_mode: Mapped[str] = mapped_column(Text, nullable=False)

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
    dimension_scores: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True
    )
    summary: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
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
        _in_check("status", QA_STATUSES, "ck_academic_qa_runs_status"),
        _in_check(
            "execution_mode", QA_EXECUTION_MODES,
            "ck_academic_qa_runs_execution_mode",
        ),
        CheckConstraint(
            "gate IS NULL OR gate IN (" +
            ",".join(f"'{v}'" for v in QA_GATES) + ")",
            name="ck_academic_qa_runs_gate",
        ),
        CheckConstraint(
            "finding_count >= 0 AND blocking_count >= 0 AND "
            "error_count >= 0 AND warning_count >= 0 AND info_count >= 0",
            name="ck_academic_qa_runs_counts",
        ),
        CheckConstraint(
            "duration_ms IS NULL OR duration_ms >= 0",
            name="ck_academic_qa_runs_duration",
        ),
        Index("ix_academic_qa_runs_project", "project_id"),
        Index("ix_academic_qa_runs_report", "report_id"),
        Index(
            "ix_academic_qa_runs_context",
            "report_id", "manuscript_version_id",
            "context_hash", "m31_version", "rules_version",
        ),
        Index(
            "ux_academic_qa_runs_completed",
            "report_id", "manuscript_version_id",
            "context_hash", "m31_version", "rules_version",
            unique=True,
            postgresql_where=text("status = 'completed'"),
        ),
    )


class AcademicQAFinding(Base, UUIDPKMixin):
    __tablename__ = "academic_qa_findings"

    qa_run_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("academic_qa_runs.id", ondelete="CASCADE"),
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
    claim_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("claims.id", ondelete="SET NULL"),
        nullable=True,
    )
    citation_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("citation_identities.id", ondelete="SET NULL"),
        nullable=True,
    )

    rule_id: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)

    location: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    evidence: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    classification: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'open'")
    )
    remediation: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    finding_meta: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        _in_check("category", QA_CATEGORIES, "ck_academic_qa_findings_category"),
        _in_check("severity", QA_SEVERITIES, "ck_academic_qa_findings_severity"),
        _in_check(
            "classification", QA_CLASSIFICATIONS,
            "ck_academic_qa_findings_classification",
        ),
        _in_check(
            "status", QA_FINDING_STATUSES,
            "ck_academic_qa_findings_status",
        ),
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="ck_academic_qa_findings_confidence",
        ),
        Index("ix_academic_qa_findings_run", "qa_run_id"),
        Index(
            "ix_academic_qa_findings_project_category",
            "project_id", "category",
        ),
        Index(
            "ix_academic_qa_findings_run_severity",
            "qa_run_id", "severity",
        ),
    )
