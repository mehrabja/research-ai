"""Research plan mutation schemas."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ResearchPlanSectionWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    section_key: str = Field(..., min_length=1, max_length=128)
    title: str = Field(..., min_length=1, max_length=500)
    purpose: str | None = None
    section_type: str = Field(..., min_length=1, max_length=64)
    display_order: int = Field(..., ge=0, le=1000)
    required: bool = False
    word_budget: int = Field(default=0, ge=0, le=1_000_000)
    budget_weight: float = Field(default=0, ge=0, le=1_000_000)
    evidence_coverage_target: float = Field(default=0, ge=0, le=1)
    status: str = "active"


class ResearchEvidenceRequirementWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requirement_key: str = Field(..., min_length=1, max_length=255)
    section_key: str = Field(..., min_length=1, max_length=128)
    requirement_type: str = Field(..., min_length=1, max_length=64)
    description: str = Field(..., min_length=1)
    required: bool = True
    priority: int = Field(default=0, ge=0)
    min_sources: int | None = Field(default=None, ge=0)
    max_sources: int | None = Field(default=None, ge=0)
    preferred_paper_types: list[str] | None = None
    preferred_research_designs: list[str] | None = None
    max_age_years: int | None = Field(default=None, ge=0)
    full_text_required: bool = False
    min_relevance_score: float | None = Field(default=None, ge=0, le=1)
    coverage_weight: float = Field(default=1, ge=0)


class ResearchPlanDependencyWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    upstream_section_key: str = Field(..., min_length=1, max_length=128)
    downstream_section_key: str = Field(..., min_length=1, max_length=128)
    dependency_type: str = Field(default="requires", min_length=1, max_length=32)


class ResearchPlanPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    research_objective_snapshot: str | None = None
    research_questions_snapshot: list[Any] | None = None
    hypotheses_snapshot: list[Any] | None = None
    budget: dict[str, Any] | None = None
    sections: list[ResearchPlanSectionWrite] | None = None
    evidence_requirements: list[ResearchEvidenceRequirementWrite] | None = None
    dependencies: list[ResearchPlanDependencyWrite] | None = None
    expected_version: int | None = Field(default=None, ge=1)
