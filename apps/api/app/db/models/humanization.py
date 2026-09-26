from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
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

from app.db.base import Base, CreatedAtMixin, TimestampMixin, UUIDPKMixin


def _in_check(
    column: str,
    values: tuple[str, ...],
    name: str,
) -> CheckConstraint:
    """
    Create a reusable SQL CHECK constraint for a closed set of values.
    """
    escaped_values = ",".join(f"'{value}'" for value in values)

    return CheckConstraint(
        f"{column} IN ({escaped_values})",
        name=name,
    )


# ============================================================================
# Humanization Run
# ============================================================================

class HumanizationRun(Base, UUIDPKMixin, CreatedAtMixin):
    """
    Represents one execution of the Humanization Engine.

    A run can happen:
    - before translation
    - after translation
    - on a manuscript (M32)

    The run stores configuration, detection scores, usage and final status.
    """

    __tablename__ = "humanization_runs"

    report_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey(
            "reports.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    generation_run_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey(
            "generation_runs.id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )

    translation_run_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey(
            "translation_runs.id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )

    stage: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    language: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    domain: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # HumanizationPolicy serialized as JSON.
    policy_json: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    detection_score_before: Mapped[Decimal | None] = mapped_column(
        Numeric,
        nullable=True,
    )

    detection_score_after: Mapped[Decimal | None] = mapped_column(
        Numeric,
        nullable=True,
    )

    cost_usd: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 8),
        nullable=True,
    )

    tokens_used: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # --- M32 extensions (nullable, additive) ---
    manuscript_version_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("manuscript_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    manuscript_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("manuscripts.id", ondelete="SET NULL"),
        nullable=True,
    )
    mode: Mapped[str | None] = mapped_column(
        Text, nullable=True,
    )
    m32_version: Mapped[str | None] = mapped_column(
        Text, nullable=True,
    )
    context_hash: Mapped[str | None] = mapped_column(
        Text, nullable=True,
    )
    gate: Mapped[str | None] = mapped_column(
        Text, nullable=True,
    )
    preservation_summary: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True,
    )

    __table_args__ = (
        _in_check(
            "stage",
            (
                "pre_translation",
                "post_translation",
                "manuscript",
            ),
            "ck_humanization_runs_stage",
        ),
        _in_check(
            "status",
            (
                "running",
                "success",
                "partial",
                "budget_exceeded",
                "failed",
            ),
            "ck_humanization_runs_status",
        ),
        CheckConstraint(
            "mode IS NULL OR mode IN "
            "('conservative','academic','natural_academic',"
            "'journal_targeted')",
            name="ck_humanization_runs_mode",
        ),
        CheckConstraint(
            "gate IS NULL OR gate IN "
            "('pass','pass_with_warnings','rejected')",
            name="ck_humanization_runs_gate",
        ),
        CheckConstraint(
            "tokens_used IS NULL OR tokens_used >= 0",
            name="ck_humanization_runs_tokens",
        ),
        CheckConstraint(
            "detection_score_before IS NULL "
            "OR (detection_score_before >= 0 "
            "AND detection_score_before <= 1)",
            name="ck_humanization_runs_detection_before",
        ),
        CheckConstraint(
            "detection_score_after IS NULL "
            "OR (detection_score_after >= 0 "
            "AND detection_score_after <= 1)",
            name="ck_humanization_runs_detection_after",
        ),
        CheckConstraint(
            "cost_usd IS NULL OR cost_usd >= 0",
            name="ck_humanization_runs_cost",
        ),
        Index(
            "ix_humanization_runs_report_stage",
            "report_id",
            "stage",
        ),
        Index(
            "ix_humanization_runs_report_created",
            "report_id",
            "created_at",
        ),
        Index(
            "ix_humanization_runs_mv",
            "manuscript_version_id",
            postgresql_where=text("manuscript_version_id IS NOT NULL"),
        ),
        Index(
            "ux_humanization_runs_m32_completed",
            "manuscript_version_id", "context_hash",
            "m32_version", "mode",
            unique=True,
            postgresql_where=text(
                "stage = 'manuscript' AND status = 'success' "
                "AND manuscript_version_id IS NOT NULL"
            ),
        ),
    )


# ============================================================================
# Humanization Iteration
# ============================================================================

class HumanizationIteration(Base, UUIDPKMixin, CreatedAtMixin):
    """
    Represents one iteration inside a HumanizationRun.

    The iteration stores:
    - detection snapshot
    - flagged segments
    - rewritten segments
    - resulting score
    - cost
    - M32: preservation result, QA impact, acceptance flag
    """

    __tablename__ = "humanization_iterations"

    humanization_run_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey(
            "humanization_runs.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    iteration_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    detection_snapshot: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    flagged_segments: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    rewritten_segments: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    detection_score_mean: Mapped[Decimal | None] = mapped_column(
        Numeric,
        nullable=True,
    )

    cost_usd: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 8),
        nullable=True,
    )

    # --- M32 extensions (nullable, additive) ---
    preservation_result: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True,
    )
    qa_impact: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True,
    )
    accepted: Mapped[bool | None] = mapped_column(
        Boolean, nullable=True,
    )

    __table_args__ = (
        UniqueConstraint(
            "humanization_run_id",
            "iteration_index",
            name="ux_humanization_iterations_run_index",
        ),
        CheckConstraint(
            "iteration_index >= 0",
            name="ck_humanization_iterations_index",
        ),
        CheckConstraint(
            "detection_score_mean IS NULL "
            "OR (detection_score_mean >= 0 "
            "AND detection_score_mean <= 1)",
            name="ck_humanization_iterations_score_range",
        ),
        CheckConstraint(
            "cost_usd IS NULL OR cost_usd >= 0",
            name="ck_humanization_iterations_cost",
        ),
        Index(
            "ix_humanization_iterations_run_index",
            "humanization_run_id",
            "iteration_index",
        ),
    )


# ============================================================================
# Humanization Rewrite
# ============================================================================

class HumanizationRewrite(Base, UUIDPKMixin, CreatedAtMixin):
    """
    Stores the before/after text of an individual rewrite.

    This table is part of the audit trail.
    """

    __tablename__ = "humanization_rewrites"

    humanization_run_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey(
            "humanization_runs.id",
            ondelete="CASCADE",
        ),
        nullable=True,
    )

    iteration_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey(
            "humanization_iterations.id",
            ondelete="CASCADE",
        ),
        nullable=True,
    )

    segment_id: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    layer: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    prompt_version: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    model: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    text_before: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    text_after: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    preservation_ok: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
    )

    cost_usd: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 8),
        nullable=True,
    )

    idempotency_key: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        unique=True,
    )

    __table_args__ = (
        CheckConstraint(
            "cost_usd IS NULL OR cost_usd >= 0",
            name="ck_humanization_rewrites_cost",
        ),
        Index(
            "ix_humanization_rewrites_run",
            "humanization_run_id",
        ),
        Index(
            "ix_humanization_rewrites_iteration",
            "iteration_id",
        ),
        Index(
            "ix_humanization_rewrites_segment",
            "segment_id",
        ),
    )


# ============================================================================
# Convergence Run
# ============================================================================

class ConvergenceRun(Base, UUIDPKMixin, CreatedAtMixin):
    """
    Represents the closed-loop convergence process.

    Example trajectory:

        0.61 -> 0.43 -> 0.32 -> 0.27 -> 0.24

    The best version is tracked separately from the latest iteration.
    """

    __tablename__ = "convergence_runs"

    report_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey(
            "reports.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    humanization_run_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey(
            "humanization_runs.id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )

    language: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    domain: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    target_threshold: Mapped[Decimal] = mapped_column(
        Numeric,
        nullable=False,
        server_default=text("0.25"),
    )

    policy_json: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    initial_score: Mapped[Decimal | None] = mapped_column(
        Numeric,
        nullable=True,
    )

    final_score: Mapped[Decimal | None] = mapped_column(
        Numeric,
        nullable=True,
    )

    best_score: Mapped[Decimal | None] = mapped_column(
        Numeric,
        nullable=True,
    )

    best_iteration_index: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    iterations_executed: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    total_cost_usd: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 8),
        nullable=True,
    )

    total_tokens: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    total_duration_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    needs_human_attention: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    __table_args__ = (
        _in_check(
            "status",
            (
                "running",
                "converged",
                "max_iterations_reached",
                "plateau_detected",
                "budget_exceeded",
                "failed",
                "stopped",
            ),
            "ck_convergence_runs_status",
        ),
        CheckConstraint(
            "target_threshold >= 0 AND target_threshold <= 1",
            name="ck_convergence_runs_target_threshold",
        ),
        CheckConstraint(
            "initial_score IS NULL "
            "OR (initial_score >= 0 AND initial_score <= 1)",
            name="ck_convergence_runs_initial_score",
        ),
        CheckConstraint(
            "final_score IS NULL "
            "OR (final_score >= 0 AND final_score <= 1)",
            name="ck_convergence_runs_final_score",
        ),
        CheckConstraint(
            "best_score IS NULL "
            "OR (best_score >= 0 AND best_score <= 1)",
            name="ck_convergence_runs_best_score",
        ),
        CheckConstraint(
            "best_iteration_index IS NULL OR best_iteration_index >= 0",
            name="ck_convergence_runs_best_iteration",
        ),
        CheckConstraint(
            "iterations_executed IS NULL OR iterations_executed >= 0",
            name="ck_convergence_runs_iterations_executed",
        ),
        CheckConstraint(
            "total_cost_usd IS NULL OR total_cost_usd >= 0",
            name="ck_convergence_runs_total_cost",
        ),
        CheckConstraint(
            "total_tokens IS NULL OR total_tokens >= 0",
            name="ck_convergence_runs_total_tokens",
        ),
        CheckConstraint(
            "total_duration_ms IS NULL OR total_duration_ms >= 0",
            name="ck_convergence_runs_duration",
        ),
        Index(
            "ix_convergence_runs_report_created",
            "report_id",
            "created_at",
        ),
        Index(
            "ix_convergence_runs_report_status",
            "report_id",
            "status",
        ),
    )


# ============================================================================
# Convergence Iteration
# ============================================================================

class ConvergenceIteration(Base, UUIDPKMixin, CreatedAtMixin):
    """
    One iteration inside the Convergence Loop.
    """

    __tablename__ = "convergence_iterations"

    convergence_run_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey(
            "convergence_runs.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    iteration_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    strategy_name: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    score_before: Mapped[Decimal] = mapped_column(
        Numeric,
        nullable=False,
    )

    score_after: Mapped[Decimal] = mapped_column(
        Numeric,
        nullable=False,
    )

    improvement: Mapped[Decimal | None] = mapped_column(
        Numeric,
        nullable=True,
    )

    flagged_segment_ids: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    rewritten_segment_ids: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    preservation_failures: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )

    cost_usd: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 8),
        nullable=True,
    )

    tokens_used: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    detection_snapshot: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    __table_args__ = (
        UniqueConstraint(
            "convergence_run_id",
            "iteration_index",
            name="ux_convergence_iterations_run_index",
        ),
        CheckConstraint(
            "iteration_index >= 0",
            name="ck_convergence_iterations_index",
        ),
        CheckConstraint(
            "score_before >= 0 AND score_before <= 1",
            name="ck_convergence_iterations_score_before",
        ),
        CheckConstraint(
            "score_after >= 0 AND score_after <= 1",
            name="ck_convergence_iterations_score_after",
        ),
        CheckConstraint(
            "improvement IS NULL OR improvement >= -1 AND improvement <= 1",
            name="ck_convergence_iterations_improvement",
        ),
        CheckConstraint(
            "preservation_failures >= 0",
            name="ck_convergence_iterations_preservation_failures",
        ),
        CheckConstraint(
            "cost_usd IS NULL OR cost_usd >= 0",
            name="ck_convergence_iterations_cost",
        ),
        CheckConstraint(
            "tokens_used IS NULL OR tokens_used >= 0",
            name="ck_convergence_iterations_tokens",
        ),
        Index(
            "ix_convergence_iterations_run_index",
            "convergence_run_id",
            "iteration_index",
        ),
    )


# ============================================================================
# Best Snapshot
# ============================================================================

class ConvergenceBestSnapshot(Base, UUIDPKMixin, CreatedAtMixin):
    """
    Stores the best-scoring version observed during a convergence run.

    One best snapshot exists per convergence run.
    """

    __tablename__ = "convergence_best_snapshots"

    convergence_run_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey(
            "convergence_runs.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        unique=True,
    )

    iteration_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    score: Mapped[Decimal] = mapped_column(
        Numeric,
        nullable=False,
    )

    segments_json: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "iteration_index >= 0",
            name="ck_convergence_best_snapshot_iteration",
        ),
        CheckConstraint(
            "score >= 0 AND score <= 1",
            name="ck_convergence_best_snapshot_score",
        ),
    )


# ============================================================================
# Convergence Strategy
# ============================================================================

class ConvergenceStrategy(Base, UUIDPKMixin, TimestampMixin):
    """
    Configurable convergence strategy.

    Strategies are stored in the DB so the strategy order and prompts can
    be changed without redeploying application code.
    """

    __tablename__ = "convergence_strategies"

    name: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        unique=True,
    )

    order_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    model: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    temperature: Mapped[Decimal | None] = mapped_column(
        Numeric,
        nullable=True,
    )

    scope: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    prompt_template: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    techniques: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
    )

    version: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'1.0.0'"),
    )

    __table_args__ = (
        CheckConstraint(
            "order_index >= 0",
            name="ck_convergence_strategies_order_index",
        ),
        CheckConstraint(
            "temperature IS NULL OR temperature >= 0",
            name="ck_convergence_strategies_temperature",
        ),
        Index(
            "ix_convergence_strategies_active_order",
            "active",
            "order_index",
        ),
    )
