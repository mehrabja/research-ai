"""M24 — Research plan schemas."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ResearchPlanSectionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: uuid.UUID
    plan_id: uuid.UUID
    section_key: str
    title: str
    purpose: str | None
    section_type: str
    display_order: int
    required: bool
    word_budget: int
    budget_weight: float
    evidence_coverage_target: float
    status: str


class ResearchEvidenceRequirementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: uuid.UUID
    plan_id: uuid.UUID
    section_id: uuid.UUID
    requirement_key: str
    requirement_type: str
    description: str
    required: bool
    priority: int
    min_sources: int | None
    max_sources: int | None
    preferred_paper_types: list[str] | None
    preferred_research_designs: list[str] | None
    max_age_years: int | None
    full_text_required: bool
    min_relevance_score: float | None
    coverage_weight: float


class ResearchPlanDependencyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: uuid.UUID
    plan_id: uuid.UUID
    upstream_section_id: uuid.UUID
    downstream_section_id: uuid.UUID
    dependency_type: str


class ResearchPlanCoverageRead(BaseModel):
    model_config = ConfigDict(extra="forbid")
    coverage_score: float
    coverage_state: str
    per_requirement: list[dict[str, Any]] = Field(default_factory=list)


class ResearchPlanValidationRead(BaseModel):
    model_config = ConfigDict(extra="forbid")
    validation_status: str
    validation_errors: list[str] = Field(default_factory=list)
    completeness_score: float | None = None


class ResearchPlanRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: uuid.UUID
    project_id: uuid.UUID
    version: int
    status: str
    planner_version: str
    planning_mode: str
    context_hash: str
    literature_run_id: uuid.UUID | None
    domain_id: uuid.UUID | None
    paper_type_code: str | None
    research_design_code: str | None
    research_objective_snapshot: str | None
    research_questions_snapshot: list[Any] | None
    hypotheses_snapshot: list[Any] | None
    budget: dict[str, Any]
    completeness_score: float | None
    coverage_score: float | None
    validation_status: str
    validation_errors: list[Any] | None
    coverage_summary: dict[str, Any] | None
    supersedes_plan_id: uuid.UUID | None
    created_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
    sections: list[ResearchPlanSectionRead] = Field(default_factory=list)
    evidence_requirements: list[ResearchEvidenceRequirementRead] = Field(
        default_factory=list
    )
    dependencies: list[ResearchPlanDependencyRead] = Field(
        default_factory=list
    )


class ResearchPlanRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: uuid.UUID
    project_id: uuid.UUID
    plan_id: uuid.UUID | None
    context_hash: str
    planner_version: str
    status: str
    planning_mode: str
    llm_provider: str | None
    llm_model: str | None
    duration_ms: int | None
    error_message: str | None
    created_at: datetime


class ResearchPlanGenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    force: bool = False
    async_: bool = Field(default=True, alias="async")


class ResearchPlanGenerateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: str
    job_id: uuid.UUID | None = None
    plan: ResearchPlanRead | None = None


class ResearchPlanVersionListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[ResearchPlanRead]
    total: int
    limit: int
    offset: int
