"""M29 — Experiment Result ORM model (run-scoped)."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPKMixin
from app.domain.technical_intelligence import (
    EXPERIMENT_RESULT_TYPES,
    RESULT_STATUSES,
)


def _in_check(col: str, values: tuple[str, ...], name: str) -> CheckConstraint:
    return CheckConstraint(
        f"{col} IN (" + ",".join(f"'{v}'" for v in values) + ")",
        name=name,
    )


class ExperimentResult(Base, UUIDPKMixin):
    __tablename__ = "experiment_results"

    technical_intelligence_run_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey(
            "technical_intelligence_runs.id", ondelete="CASCADE",
        ),
        nullable=False,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    report_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("reports.id", ondelete="CASCADE"),
        nullable=True,
    )
    manuscript_version_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("manuscript_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    technical_fact_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("technical_facts.id", ondelete="SET NULL"),
        nullable=True,
    )
    project_file_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("project_files.id", ondelete="RESTRICT"),
        nullable=False,
    )
    result_type: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    value: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    unit: Mapped[str | None] = mapped_column(Text, nullable=True)
    experiment_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    provenance: Mapped[dict] = mapped_column(JSONB, nullable=False)
    context_hash: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'parsed'")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        _in_check(
            "result_type", EXPERIMENT_RESULT_TYPES,
            "ck_experiment_results_type",
        ),
        _in_check("status", RESULT_STATUSES, "ck_experiment_results_status"),
        Index(
            "ix_experiment_results_run",
            "technical_intelligence_run_id",
        ),
        Index(
            "ix_experiment_results_run_type",
            "technical_intelligence_run_id", "result_type",
        ),
        Index(
            "ix_experiment_results_run_key",
            "technical_intelligence_run_id", "experiment_key",
        ),
        Index("ix_experiment_results_file", "project_file_id"),
    )
