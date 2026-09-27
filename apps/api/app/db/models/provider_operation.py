"""M39 provider-operation audit ledger."""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAtMixin, UUIDPKMixin


class ProviderOperation(Base, UUIDPKMixin, CreatedAtMixin):
    __tablename__ = "provider_operations"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
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
    capability: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    input_tokens: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    cost_raw_usd: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)
    cost_billable_usd: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)
    error_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    operation_metadata: Mapped[dict | None] = mapped_column(
        "metadata", JSONB, nullable=True
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    __table_args__ = (
        CheckConstraint(
            "capability IN ('generation','embedding','translation','detection','search','reranking')",
            name="ck_provider_operations_capability",
        ),
        CheckConstraint(
            "status IN ('started','succeeded','failed','canceled')",
            name="ck_provider_operations_status",
        ),
        CheckConstraint(
            "input_tokens IS NULL OR input_tokens >= 0",
            name="ck_provider_operations_input_tokens",
        ),
        CheckConstraint(
            "output_tokens IS NULL OR output_tokens >= 0",
            name="ck_provider_operations_output_tokens",
        ),
        CheckConstraint(
            "total_tokens IS NULL OR total_tokens >= 0",
            name="ck_provider_operations_total_tokens",
        ),
        CheckConstraint(
            "duration_ms IS NULL OR duration_ms >= 0",
            name="ck_provider_operations_duration",
        ),
        CheckConstraint(
            "cost_raw_usd IS NULL OR cost_raw_usd >= 0",
            name="ck_provider_operations_cost_raw",
        ),
        CheckConstraint(
            "cost_billable_usd IS NULL OR cost_billable_usd >= 0",
            name="ck_provider_operations_cost_billable",
        ),
        UniqueConstraint(
            "workspace_id",
            "idempotency_key",
            name="ux_provider_operations_workspace_idempotency",
        ),
        Index(
            "ix_provider_operations_workspace_started",
            "workspace_id",
            "started_at",
        ),
        Index(
            "ix_provider_operations_workspace_operation",
            "workspace_id",
            "operation",
            "started_at",
        ),
        Index(
            "ix_provider_operations_provider_model",
            "provider",
            "model",
            "started_at",
        ),
        Index("ix_provider_operations_job", "job_id"),
        Index("ix_provider_operations_request", "request_id"),
    )
