"""M27 — Manuscript Architect Pydantic schemas."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SourceConstraintsRead(BaseModel):
    model_config = ConfigDict(extra="forbid")
    min_sources: int | None = None
    max_sources: int | None = None
    preferred_paper_types: list[str] = Field(default_factory=list)
    preferred_research_designs: list[str] = Field(default_factory=list)
    max_age_years: int | None = None
    full_text_required: bool = False
    min_relevance_score: float | None = None


class EvidenceRequirementSnapshotRead(BaseModel):
    model_config = ConfigDict(extra="forbid")
    requirement_id: str
    requirement_key: str
    requirement_type: str
    required: bool
    priority: int
    min_sources: int | None = None
    max_sources: int | None = None
    preferred_paper_types: list[str] = Field(default_factory=list)
    preferred_research_designs: list[str] = Field(default_factory=list)
    max_age_years: int | None = None
    full_text_required: bool = False
    min_relevance_score: float | None = None
    coverage_weight: float
    retrieval_intents: list[str] = Field(default_factory=list)


class ResearchContractRead(BaseModel):
    model_config = ConfigDict(extra="forbid")
    section_key: str
    research_objective: str
    retrieval_intents: list[str] = Field(default_factory=list)
    evidence_requirements: list[EvidenceRequirementSnapshotRead] = Field(
        default_factory=list
    )
    source_constraints: SourceConstraintsRead
    coverage_target: float
    citation_required: bool
    intent_mapping_version: str


class ManuscriptSectionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: uuid.UUID
    manuscript_version_id: uuid.UUID
    section_key: str
    title: str
    purpose: str | None
    section_type: str
    display_order: int
    required: bool
    word_budget: int
    budget_weight: float
    evidence_coverage_target: float
    research_objective: str | None
    writing_objective: str | None
    citation_required: bool
    research_contract: ResearchContractRead
    status: str


class ManuscriptVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: uuid.UUID
    manuscript_id: uuid.UUID
    version: int
    status: str
    architecture_version: str
    template_version: str
    research_plan_id: uuid.UUID
    research_plan_version: int
    research_plan_context_hash: str
    context_hash: str
    title: str
    title_rationale: str | None
    abstract_direction: dict[str, Any] | None
    word_target: int
    created_at: datetime


class ManuscriptSectionDependencyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: uuid.UUID
    upstream_section_id: uuid.UUID
    downstream_section_id: uuid.UUID
    dependency_type: str


class ManuscriptRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: uuid.UUID
    report_id: uuid.UUID
    current_version_id: uuid.UUID | None
    status: str
    architecture_version: str
    template_version: str
    context_hash: str
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None


class ManuscriptCurrentRead(BaseModel):
    model_config = ConfigDict(extra="forbid")
    manuscript: ManuscriptRead
    version: ManuscriptVersionRead
    sections: list[ManuscriptSectionRead]
    dependencies: list[ManuscriptSectionDependencyRead]
    research_order: list[str]


class ManuscriptGenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    force: bool = False
    async_: bool = Field(default=True, alias="async")


class ManuscriptGenerateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: str
    job_id: uuid.UUID | None = None
    manuscript_id: uuid.UUID | None = None
    version_id: uuid.UUID | None = None
    context_hash: str | None = None
    section_count: int | None = None
    research_order: list[str] = Field(default_factory=list)


class ManuscriptVersionListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[ManuscriptVersionRead]
    total: int
    limit: int
    offset: int


class ManuscriptValidationRead(BaseModel):
    model_config = ConfigDict(extra="forbid")
    validation_status: str
    validation_errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ManuscriptDraftRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: uuid.UUID
    manuscript_id: uuid.UUID
    updated_by: uuid.UUID | None
    base_version_id: uuid.UUID | None
    sections: list[Any] | None
    draft_hash: str
    created_at: datetime
    updated_at: datetime


class ManuscriptDraftUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    base_version_id: uuid.UUID | None = None
    sections: list[Any] = Field(default_factory=list)
