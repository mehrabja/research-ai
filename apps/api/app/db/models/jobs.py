"""SQLAlchemy model for the durable job queue."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPKMixin

_JOB_STATUSES = (
    "queued",
    "processing",
    "retrying",
    "completed",
    "failed",
    "cancelled",
)


class Job(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "jobs"

    job_type: Mapped[str] = mapped_column(Text, nullable=False)

    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'queued'")
    )

    priority: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )

    payload: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )

    report_id: Mapped[PGUUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("reports.id", ondelete="SET NULL"),
        nullable=True,
    )
    user_id: Mapped[PGUUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    attempt_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    max_attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("3")
    )

    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    failed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    heartbeat_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    worker_id: Mapped[str | None] = mapped_column(Text, nullable=True)

    last_error_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_error_message: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )

    idempotency_key: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            "status IN (" + ",".join(f"'{s}'" for s in _JOB_STATUSES) + ")",
            name="ck_jobs_status",
        ),
        CheckConstraint("priority >= 0", name="ck_jobs_priority_nonneg"),
        CheckConstraint(
            "attempt_count >= 0", name="ck_jobs_attempt_count_nonneg"
        ),
        CheckConstraint(
            "max_attempts >= 1", name="ck_jobs_max_attempts_pos"
        ),
        CheckConstraint(
            "attempt_count <= max_attempts",
            name="ck_jobs_attempt_within_max",
        ),
        CheckConstraint(
            "status <> 'processing' OR "
            "(worker_id IS NOT NULL AND "
            "heartbeat_at IS NOT NULL AND "
            "started_at IS NOT NULL)",
            name="ck_jobs_processing_lease",
        ),
        CheckConstraint(
            "status <> 'completed' OR completed_at IS NOT NULL",
            name="ck_jobs_completed_at_required",
        ),
        CheckConstraint(
            "status <> 'failed' OR failed_at IS NOT NULL",
            name="ck_jobs_failed_at_required",
        ),
        Index(
            "ix_jobs_ready",
            "status",
            "available_at",
            "priority",
            "created_at",
            postgresql_where=text("status IN ('queued', 'retrying')"),
        ),
        Index("ix_jobs_report", "report_id"),
        Index(
            "ix_jobs_stale",
            "status",
            "heartbeat_at",
            postgresql_where=text("status = 'processing'"),
        ),
        Index("ix_jobs_user_created", "user_id", "created_at"),
        Index(
            "ux_jobs_idempotency_key",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
        ),
    )
