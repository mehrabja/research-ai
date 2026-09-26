"""M29 — Metric ORM model (run-scoped, with status)."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
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


class Metric(Base, UUIDPKMixin):
    __tablename__ = "metrics"

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
    experiment_result_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("experiment_results.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_name: Mapped[str] = mapped_column(Text, nullable=False)
    value_numeric: Mapped[float | None] = mapped_column(Float, nullable=True)
    value_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    unit: Mapped[str | None] = mapped_column(Text, nullable=True)
    split: Mapped[str | None] = mapped_column(Text, nullable=True)
    direction: Mapped[str | None] = mapped_column(Text, nullable=True)
    baseline_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    delta_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_primary: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
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
        CheckConstraint(
            "direction IS NULL OR direction IN ('higher','lower')",
            name="ck_metrics_direction",
        ),
        CheckConstraint(
            "status IN ('parsed','validated','rejected')",
            name="ck_metrics_status",
        ),
        CheckConstraint(
            "value_numeric IS NOT NULL OR value_text IS NOT NULL",
            name="ck_metrics_value_present",
        ),
        Index("ix_metrics_run", "technical_intelligence_run_id"),
        Index(
            "ix_metrics_run_normalized",
            "technical_intelligence_run_id", "normalized_name",
        ),
        Index("ix_metrics_result", "experiment_result_id"),
    )
