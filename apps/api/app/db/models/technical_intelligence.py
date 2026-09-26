"""M29 — Technical Intelligence Run ORM model (idempotency anchor)."""
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
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPKMixin
from app.domain.technical_intelligence import (
    TECHNICAL_INTELLIGENCE_RUN_STATUSES,
)


def _in_check(col: str, values: tuple[str, ...], name: str) -> CheckConstraint:
    return CheckConstraint(
        f"{col} IN (" + ",".join(f"'{v}'" for v in values) + ")",
        name=name,
    )


class TechnicalIntelligenceRun(Base, UUIDPKMixin):
    __tablename__ = "technical_intelligence_runs"

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
    context_hash: Mapped[str] = mapped_column(Text, nullable=False)
    m29_version: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)

    fact_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    result_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    metric_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )

    input_snapshot: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True
    )
    output_summary: Mapped[dict | None] = mapped_column(
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
            "status",
            TECHNICAL_INTELLIGENCE_RUN_STATUSES,
            "ck_technical_intelligence_runs_status",
        ),
        CheckConstraint(
            "fact_count >= 0 AND result_count >= 0 AND metric_count >= 0",
            name="ck_technical_intelligence_runs_counts",
        ),
        CheckConstraint(
            "duration_ms IS NULL OR duration_ms >= 0",
            name="ck_technical_intelligence_runs_duration",
        ),
        Index("ix_technical_intelligence_runs_project", "project_id"),
        Index(
            "ix_technical_intelligence_runs_context",
            "project_id", "context_hash", "m29_version",
        ),
        Index(
            "ux_technical_intelligence_runs_completed",
            "project_id", "context_hash", "m29_version",
            unique=True,
            postgresql_where=text("status = 'completed'"),
        ),
    )
