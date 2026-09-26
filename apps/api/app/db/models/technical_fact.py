"""M29 — Technical Fact ORM model (run-scoped)."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
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
    FACT_STATUSES,
    TECHNICAL_FACT_TYPES,
)


def _in_check(col: str, values: tuple[str, ...], name: str) -> CheckConstraint:
    return CheckConstraint(
        f"{col} IN (" + ",".join(f"'{v}'" for v in values) + ")",
        name=name,
    )


class TechnicalFact(Base, UUIDPKMixin):
    __tablename__ = "technical_facts"

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
    project_file_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("project_files.id", ondelete="CASCADE"),
        nullable=False,
    )
    code_analysis_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("code_analyses.id", ondelete="CASCADE"),
        nullable=True,
    )
    data_profile_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("data_profiles.id", ondelete="CASCADE"),
        nullable=True,
    )
    fact_type: Mapped[str] = mapped_column(Text, nullable=False)
    fact_key: Mapped[str] = mapped_column(Text, nullable=False)
    fact_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    normalized_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    unit: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(
        Float, nullable=False, server_default=text("1.0")
    )
    provenance: Mapped[dict] = mapped_column(JSONB, nullable=False)
    context_hash: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'extracted'")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        _in_check("fact_type", TECHNICAL_FACT_TYPES, "ck_technical_facts_type"),
        _in_check("status", FACT_STATUSES, "ck_technical_facts_status"),
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_technical_facts_confidence",
        ),
        Index("ix_technical_facts_run", "technical_intelligence_run_id"),
        Index(
            "ix_technical_facts_run_type",
            "technical_intelligence_run_id", "fact_type",
        ),
        Index(
            "ix_technical_facts_run_key",
            "technical_intelligence_run_id", "fact_key",
        ),
        Index("ix_technical_facts_project", "project_id"),
    )
