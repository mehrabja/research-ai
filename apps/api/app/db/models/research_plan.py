"""M24 — Research Planning ORM models."""
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
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPKMixin
from app.domain.research_plan import (
    RESEARCH_PLAN_DEPENDENCY_TYPES,
    RESEARCH_PLAN_MODES,
    RESEARCH_PLAN_RUN_STATUSES,
    RESEARCH_PLAN_STATUSES,
    RESEARCH_PLAN_VALIDATION_STATUSES,
)


def _in_check(col: str, values: tuple[str, ...], name: str) -> CheckConstraint:
    return CheckConstraint(
        f"{col} IN (" + ",".join(f"'{v}'" for v in values) + ")",
        name=name,
    )


class ResearchPlan(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "research_plans"

    project_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'draft'")
    )
    planner_version: Mapped[str] = mapped_column(Text, nullable=False)
    planning_mode: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'deterministic'")
    )

    context_hash: Mapped[str] = mapped_column(Text, nullable=False)
    literature_run_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("literature_intelligence_runs.id", ondelete="SET NULL"),
        nullable=True,
    )

    domain_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("research_domains.id", ondelete="SET NULL"),
        nullable=True,
    )
    paper_type_code: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("paper_types.code", ondelete="SET NULL"),
        nullable=True,
    )
    research_design_code: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("research_designs.code", ondelete="SET NULL"),
        nullable=True,
    )

    research_objective_snapshot: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    research_questions_snapshot: Mapped[list | None] = mapped_column(
        JSONB, nullable=True
    )
    hypotheses_snapshot: Mapped[list | None] = mapped_column(
        JSONB, nullable=True
    )

    budget: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    plan_meta: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    completeness_score: Mapped[Decimal | None] = mapped_column(
        Numeric, nullable=True
    )
    coverage_score: Mapped[Decimal | None] = mapped_column(
        Numeric, nullable=True
    )

    validation_status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'pending'")
    )
    validation_errors: Mapped[list | None] = mapped_column(
        JSONB, nullable=True
    )
    coverage_summary: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True
    )

    supersedes_plan_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("research_plans.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    __table_args__ = (
        _in_check("status", RESEARCH_PLAN_STATUSES,
                  "ck_research_plans_status"),
        _in_check("planning_mode", RESEARCH_PLAN_MODES,
                  "ck_research_plans_mode"),
        _in_check("validation_status", RESEARCH_PLAN_VALIDATION_STATUSES,
                  "ck_research_plans_validation_status"),
        CheckConstraint("version >= 1", name="ck_research_plans_version"),
        UniqueConstraint("project_id", "version",
                         name="ux_research_plans_project_version"),
        Index("ix_research_plans_project", "project_id"),
        Index("ix_research_plans_project_status", "project_id", "status"),
        Index("ix_research_plans_project_version", "project_id", "version"),
        Index(
            "ux_research_plans_context_completed",
            "project_id", "context_hash", "planner_version",
            unique=True,
            postgresql_where=text("status = 'ready'"),
        ),
    )


class ResearchPlanSection(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "research_plan_sections"

    plan_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("research_plans.id", ondelete="CASCADE"),
        nullable=False,
    )
    section_key: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    purpose: Mapped[str | None] = mapped_column(Text, nullable=True)
    section_type: Mapped[str] = mapped_column(Text, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False)
    required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    word_budget: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    budget_weight: Mapped[Decimal] = mapped_column(
        Numeric, nullable=False, server_default=text("0")
    )
    evidence_coverage_target: Mapped[Decimal] = mapped_column(
        Numeric, nullable=False, server_default=text("0")
    )
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'active'")
    )
    section_meta: Mapped[dict | None] = mapped_column(
        "section_meta", JSONB, nullable=True
    )

    __table_args__ = (
        UniqueConstraint("plan_id", "section_key",
                         name="ux_research_plan_sections_key"),
        UniqueConstraint("plan_id", "display_order",
                         name="ux_research_plan_sections_order"),
        CheckConstraint("display_order >= 0",
                        name="ck_research_plan_sections_order"),
        CheckConstraint("word_budget >= 0",
                        name="ck_research_plan_sections_wb"),
        CheckConstraint("budget_weight >= 0",
                        name="ck_research_plan_sections_bw"),
        CheckConstraint(
            "evidence_coverage_target >= 0 AND "
            "evidence_coverage_target <= 1",
            name="ck_research_plan_sections_ect",
        ),
        Index("ix_research_plan_sections_plan_order",
              "plan_id", "display_order"),
    )


class ResearchEvidenceRequirement(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "research_evidence_requirements"

    plan_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("research_plans.id", ondelete="CASCADE"),
        nullable=False,
    )
    section_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("research_plan_sections.id", ondelete="CASCADE"),
        nullable=False,
    )
    requirement_key: Mapped[str] = mapped_column(Text, nullable=False)
    requirement_type: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    priority: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    min_sources: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_sources: Mapped[int | None] = mapped_column(Integer, nullable=True)
    preferred_paper_types: Mapped[list | None] = mapped_column(
        JSONB, nullable=True
    )
    preferred_research_designs: Mapped[list | None] = mapped_column(
        JSONB, nullable=True
    )
    max_age_years: Mapped[int | None] = mapped_column(Integer, nullable=True)
    full_text_required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    min_relevance_score: Mapped[Decimal | None] = mapped_column(
        Numeric, nullable=True
    )
    coverage_weight: Mapped[Decimal] = mapped_column(
        Numeric, nullable=False, server_default=text("1")
    )
    requirement_meta: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True
    )

    __table_args__ = (
        UniqueConstraint("plan_id", "requirement_key",
                         name="ux_research_evidence_requirements_key"),
        CheckConstraint("min_sources IS NULL OR min_sources >= 0",
                        name="ck_rer_min"),
        CheckConstraint(
            "max_sources IS NULL OR "
            "(min_sources IS NOT NULL AND max_sources >= min_sources)",
            name="ck_rer_max_ge_min",
        ),
        CheckConstraint("priority >= 0", name="ck_rer_priority"),
        CheckConstraint("coverage_weight >= 0", name="ck_rer_weight"),
        CheckConstraint(
            "min_relevance_score IS NULL OR "
            "(min_relevance_score >= 0 AND min_relevance_score <= 1)",
            name="ck_rer_min_rel",
        ),
        Index("ix_research_evidence_requirements_plan", "plan_id"),
        Index("ix_research_evidence_requirements_section", "section_id"),
    )


class ResearchPlanDependency(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "research_plan_dependencies"

    plan_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("research_plans.id", ondelete="CASCADE"),
        nullable=False,
    )
    upstream_section_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("research_plan_sections.id", ondelete="CASCADE"),
        nullable=False,
    )
    downstream_section_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("research_plan_sections.id", ondelete="CASCADE"),
        nullable=False,
    )
    dependency_type: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'requires'")
    )
    dependency_meta: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True
    )

    __table_args__ = (
        UniqueConstraint(
            "plan_id", "upstream_section_id", "downstream_section_id",
            name="ux_research_plan_dependencies_edge",
        ),
        _in_check("dependency_type", RESEARCH_PLAN_DEPENDENCY_TYPES,
                  "ck_research_plan_dependencies_type"),
        CheckConstraint(
            "upstream_section_id <> downstream_section_id",
            name="ck_research_plan_dependencies_no_self",
        ),
        Index("ix_research_plan_dependencies_plan", "plan_id"),
    )


class ResearchPlanRun(Base):
    __tablename__ = "research_plan_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    plan_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("research_plans.id", ondelete="SET NULL"),
        nullable=True,
    )
    context_hash: Mapped[str] = mapped_column(Text, nullable=False)
    planner_version: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    planning_mode: Mapped[str] = mapped_column(Text, nullable=False)
    llm_provider: Mapped[str | None] = mapped_column(Text, nullable=True)
    llm_model: Mapped[str | None] = mapped_column(Text, nullable=True)
    input_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    output_summary: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        _in_check("status", RESEARCH_PLAN_RUN_STATUSES,
                  "ck_research_plan_runs_status"),
        _in_check("planning_mode", RESEARCH_PLAN_MODES,
                  "ck_research_plan_runs_mode"),
        CheckConstraint(
            "duration_ms IS NULL OR duration_ms >= 0",
            name="ck_research_plan_runs_duration",
        ),
        Index("ix_research_plan_runs_project", "project_id"),
        Index("ix_research_plan_runs_context",
              "project_id", "context_hash"),
        Index(
            "ux_research_plan_runs_completed",
            "project_id", "context_hash", "planner_version",
            unique=True,
            postgresql_where=text("status = 'completed'"),
        ),
    )
