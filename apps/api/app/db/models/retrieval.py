"""M26 — Retrieval run + result ORM models."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAtMixin, UUIDPKMixin
from app.domain.retrieval_advanced import RETRIEVAL_RUN_STATUSES


def _in_check(
    col: str, values: tuple[str, ...], name: str
) -> CheckConstraint:
    return CheckConstraint(
        f"{col} IN (" + ",".join(f"'{v}'" for v in values) + ")",
        name=name,
    )


class RetrievalRun(Base, UUIDPKMixin, CreatedAtMixin):
    __tablename__ = "retrieval_runs"

    project_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    report_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("reports.id", ondelete="SET NULL"),
        nullable=True,
    )
    research_plan_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("research_plans.id", ondelete="SET NULL"),
        nullable=True,
    )
    plan_section_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), nullable=True
    )
    evidence_requirement_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), nullable=True
    )
    graph_version_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("knowledge_graph_versions.id", ondelete="SET NULL"),
        nullable=True,
    )

    query: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_query: Mapped[str] = mapped_column(Text, nullable=False)
    query_hash: Mapped[str] = mapped_column(Text, nullable=False)
    context_hash: Mapped[str] = mapped_column(Text, nullable=False)

    retrieval_version: Mapped[str] = mapped_column(Text, nullable=False)
    ranking_model_version: Mapped[str] = mapped_column(
        Text, nullable=False
    )
    status: Mapped[str] = mapped_column(Text, nullable=False)

    candidate_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    final_result_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    duration_ms: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    error_message: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )

    input_snapshot: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True
    )
    output_summary: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True
    )
    coverage: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    warnings: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        _in_check(
            "status", RETRIEVAL_RUN_STATUSES,
            "ck_retrieval_runs_status",
        ),
        CheckConstraint(
            "candidate_count >= 0 AND final_result_count >= 0",
            name="ck_retrieval_runs_counts",
        ),
        CheckConstraint(
            "duration_ms IS NULL OR duration_ms >= 0",
            name="ck_retrieval_runs_duration",
        ),
        Index("ix_retrieval_runs_project", "project_id"),
        Index(
            "ix_retrieval_runs_project_context",
            "project_id", "context_hash",
        ),
        Index(
            "ix_retrieval_runs_project_query",
            "project_id", "query_hash",
        ),
        Index(
            "ux_retrieval_runs_completed",
            "project_id", "context_hash",
            unique=True,
            postgresql_where=text("status = 'completed'"),
        ),
    )


class RetrievalResult(Base, UUIDPKMixin, CreatedAtMixin):
    __tablename__ = "retrieval_results"

    retrieval_run_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("retrieval_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    chunk_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("chunks.id", ondelete="CASCADE"),
        nullable=True,
    )
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("sources.id", ondelete="CASCADE"),
        nullable=True,
    )
    rank: Mapped[int] = mapped_column(Integer, nullable=False)

    vector_score: Mapped[float | None] = mapped_column(
        Numeric, nullable=True
    )
    lexical_score: Mapped[float | None] = mapped_column(
        Numeric, nullable=True
    )
    graph_score: Mapped[float | None] = mapped_column(
        Numeric, nullable=True
    )
    memory_score: Mapped[float | None] = mapped_column(
        Numeric, nullable=True
    )
    quality_score: Mapped[float | None] = mapped_column(
        Numeric, nullable=True
    )
    diversity_penalty: Mapped[float | None] = mapped_column(
        Numeric, nullable=True
    )
    final_score: Mapped[float] = mapped_column(Numeric, nullable=False)

    retrieval_stage: Mapped[str] = mapped_column(Text, nullable=False)
    retrieval_reason: Mapped[list] = mapped_column(JSONB, nullable=False)
    graph_distance: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    memory_match: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), nullable=True
    )
    result_meta: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True
    )

    __table_args__ = (
        CheckConstraint("rank >= 1", name="ck_retrieval_results_rank"),
        UniqueConstraint(
            "retrieval_run_id", "rank",
            name="ux_retrieval_results_run_rank",
        ),
        Index(
            "ix_retrieval_results_run",
            "retrieval_run_id", "rank",
        ),
        Index(
            "ix_retrieval_results_project_source",
            "project_id", "source_id",
        ),
        Index(
            "ix_retrieval_results_project_chunk",
            "project_id", "chunk_id",
        ),
    )
