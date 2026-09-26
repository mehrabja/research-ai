"""M35 — Agentic orchestration ORM models."""
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
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAtMixin, UUIDPKMixin
from app.domain.orchestration import (
    FAILURE_CLASSES,
    NODE_STATUSES,
    NODE_TYPES,
    RUN_STATUSES,
)


def _in_check(col: str, values: tuple[str, ...], name: str) -> CheckConstraint:
    return CheckConstraint(
        f"{col} IN (" + ",".join(f"'{v}'" for v in values) + ")",
        name=name,
    )


class ResearchOrchestrationRun(Base, UUIDPKMixin, CreatedAtMixin):
    __tablename__ = "research_orchestration_runs"

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
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    goal: Mapped[str] = mapped_column(Text, nullable=False)
    goal_meta: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True
    )

    context_hash: Mapped[str] = mapped_column(Text, nullable=False)
    orchestration_version: Mapped[str] = mapped_column(
        Text, nullable=False
    )
    planner_version: Mapped[str] = mapped_column(Text, nullable=False)
    tool_registry_version: Mapped[str] = mapped_column(
        Text, nullable=False
    )
    strategy: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'queued'")
    )

    current_node_key: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )

    budget: Mapped[dict] = mapped_column(JSONB, nullable=False)
    budget_used: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True
    )

    approvals_required: Mapped[list | None] = mapped_column(
        JSONB, nullable=True
    )
    approvals_received: Mapped[list | None] = mapped_column(
        JSONB, nullable=True
    )

    summary: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    errors: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    checkpoint_state: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True
    )
    last_checkpoint_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    node_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    completed_node_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    failed_node_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )

    error_message: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    duration_ms: Mapped[int | None] = mapped_column(
        Integer, nullable=True
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
    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        _in_check("status", RUN_STATUSES, "ck_orchestration_runs_status"),
        CheckConstraint(
            "node_count >= 0 AND completed_node_count >= 0 AND "
            "failed_node_count >= 0",
            name="ck_orchestration_runs_counts",
        ),
        CheckConstraint(
            "duration_ms IS NULL OR duration_ms >= 0",
            name="ck_orchestration_runs_duration",
        ),
        Index(
            "ix_orchestration_runs_project", "project_id",
        ),
        Index(
            "ix_orchestration_runs_report", "report_id",
        ),
        Index(
            "ix_orchestration_runs_status", "status",
        ),
        Index(
            "ux_orchestration_runs_completed",
            "report_id", "context_hash", "orchestration_version",
            unique=True,
            postgresql_where=text("status = 'completed'"),
        ),
    )


class ResearchOrchestrationNode(Base, UUIDPKMixin, CreatedAtMixin):
    __tablename__ = "research_orchestration_nodes"

    run_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("research_orchestration_runs.id", ondelete="CASCADE"),
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

    node_key: Mapped[str] = mapped_column(Text, nullable=False)
    node_version: Mapped[str] = mapped_column(Text, nullable=False)
    node_type: Mapped[str] = mapped_column(Text, nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)

    depends_on: Mapped[list | None] = mapped_column(
        JSONB, nullable=True
    )

    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'pending'")
    )

    input_snapshot: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True
    )
    output_snapshot: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True
    )
    context_hash: Mapped[str] = mapped_column(Text, nullable=False)

    attempt: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    max_attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("3")
    )

    deterministic: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )

    error_class: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    error_message: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )

    checkpoint_meta: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True
    )

    duration_ms: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        _in_check("status", NODE_STATUSES, "ck_orchestration_nodes_status"),
        _in_check("node_type", NODE_TYPES, "ck_orchestration_nodes_type"),
        CheckConstraint(
            "error_class IS NULL OR error_class IN (" +
            ",".join(f"'{v}'" for v in FAILURE_CLASSES) + ")",
            name="ck_orchestration_nodes_error_class",
        ),
        CheckConstraint(
            "sequence >= 0",
            name="ck_orchestration_nodes_sequence",
        ),
        CheckConstraint(
            "attempt >= 0 AND max_attempts >= 1",
            name="ck_orchestration_nodes_attempt",
        ),
        CheckConstraint(
            "attempt <= max_attempts",
            name="ck_orchestration_nodes_attempt_max",
        ),
        CheckConstraint(
            "duration_ms IS NULL OR duration_ms >= 0",
            name="ck_orchestration_nodes_duration",
        ),
        UniqueConstraint(
            "run_id", "node_key", "node_version", "context_hash",
            name="ux_orchestration_nodes_idempotency",
        ),
        Index(
            "ix_orchestration_nodes_run_sequence",
            "run_id", "sequence",
        ),
        Index(
            "ix_orchestration_nodes_run_status",
            "run_id", "status",
        ),
        Index(
            "ix_orchestration_nodes_project",
            "project_id",
        ),
    )
