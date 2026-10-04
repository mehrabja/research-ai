"""Auditable AI operation ledger (M39)."""
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
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAtMixin, UUIDPKMixin

AI_OPERATION_STATUSES = ("started", "succeeded", "failed")


class AIOperation(Base, UUIDPKMixin, CreatedAtMixin):
    __tablename__ = "ai_operations"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="SET NULL"),
        nullable=True,
    )
    report_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("reports.id", ondelete="SET NULL"),
        nullable=True,
    )
    job_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="SET NULL"),
        nullable=True,
    )
    request_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    operation: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str | None] = mapped_column(Text, nullable=True)
    model: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'started'")
    )
    input_units: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_units: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_cost_usd: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 8), nullable=True
    )
    error_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    operation_metadata: Mapped[dict | None] = mapped_column(
        "metadata", JSONB, nullable=True
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('started','succeeded','failed')",
            name="ck_ai_operations_status",
        ),
        CheckConstraint(
            "input_units IS NULL OR input_units >= 0",
            name="ck_ai_operations_input_nonneg",
        ),
        CheckConstraint(
            "output_units IS NULL OR output_units >= 0",
            name="ck_ai_operations_output_nonneg",
        ),
        CheckConstraint(
            "duration_ms IS NULL OR duration_ms >= 0",
            name="ck_ai_operations_duration_nonneg",
        ),
        UniqueConstraint(
            "workspace_id",
            "operation",
            "idempotency_key",
            name="ux_ai_operations_idempotency",
        ),
        Index(
            "ix_ai_operations_workspace_created",
            "workspace_id",
            "created_at",
        ),
        Index(
            "ix_ai_operations_report_created",
            "report_id",
            "created_at",
        ),
        Index(
            "ix_ai_operations_job",
            "job_id",
        ),
    )
