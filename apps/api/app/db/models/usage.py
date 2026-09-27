"""M37 — Usage events (append-only, idempotent)."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAtMixin, UUIDPKMixin

USAGE_METRICS: tuple[str, ...] = (
    "reports_created",
    "jobs_enqueued",
    "files_uploaded",
    "storage_bytes",
    "ai_generation_units",
    "search_requests",
)

USAGE_SOURCE_TYPES: tuple[str, ...] = (
    "report",
    "job",
    "file",
    "provider_call",
    "manual",
    "system",
)


def _in_check(col: str, values: tuple[str, ...], name: str) -> CheckConstraint:
    return CheckConstraint(
        f"{col} IN (" + ",".join(f"'{v}'" for v in values) + ")",
        name=name,
    )


class UsageEvent(Base, UUIDPKMixin, CreatedAtMixin):
    __tablename__ = "usage_events"

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
    metric: Mapped[str] = mapped_column(Text, nullable=False)
    usage_class: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'internal'")
    )
    quantity: Mapped[int] = mapped_column(BigInteger, nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    source_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), nullable=True
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    # Python attribute is event_metadata (metadata is reserved on
    # SQLAlchemy declarative classes); DB column is `metadata`.
    event_metadata: Mapped[dict | None] = mapped_column(
        "metadata", JSONB, nullable=True
    )

    __table_args__ = (
        _in_check("metric", USAGE_METRICS, "ck_usage_events_metric"),
        CheckConstraint(
            "usage_class IN ('provider','internal','billable')",
            name="ck_usage_events_class",
        ),
        CheckConstraint(
            "source_type IS NULL OR "
            + "source_type IN ("
            + ",".join(f"'{v}'" for v in USAGE_SOURCE_TYPES)
            + ")",
            name="ck_usage_events_source_type",
        ),
        CheckConstraint(
            "quantity > 0", name="ck_usage_events_quantity_pos"
        ),
        Index(
            "ux_usage_events_idempotency",
            "workspace_id",
            "metric",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
        ),
        Index(
            "ix_usage_events_ws_metric_occurred",
            "workspace_id",
            "metric",
            "occurred_at",
        ),
        Index(
            "ix_usage_events_ws_occurred",
            "workspace_id",
            "occurred_at",
        ),
        Index("ix_usage_events_user", "user_id"),
    )
