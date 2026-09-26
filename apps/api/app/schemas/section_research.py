"""M28 — Section Research Pydantic schemas."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class EvidenceItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: uuid.UUID
    source_id: uuid.UUID
    chunk_id: uuid.UUID | None
    rank: int
    final_score: float
    retrieval_stage: str
    retrieval_reason: list[Any] = Field(default_factory=list)
    evidence_role: str
    matched_requirement_keys: list[str] = Field(default_factory=list)
    citation_label: str | None
    excerpt: str | None


class RequirementCoverageRead(BaseModel):
    model_config = ConfigDict(extra="forbid")
    requirement_key: str
    status: str
    matched_source_count: int
    matched_evidence_count: int
    coverage_score: float
    reason: str


class CoverageSummaryRead(BaseModel):
    model_config = ConfigDict(extra="forbid")
    coverage_version: str
    coverage_target: float
    coverage_score: float
    coverage_state: str
    per_requirement: list[RequirementCoverageRead] = Field(
        default_factory=list
    )
    warnings: list[str] = Field(default_factory=list)


class SectionResearchRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: uuid.UUID
    project_id: uuid.UUID
    report_id: uuid.UUID
    manuscript_id: uuid.UUID
    manuscript_version_id: uuid.UUID
    manuscript_section_id: uuid.UUID
    context_hash: str
    contract_hash: str
    m28_version: str
    status: str
    primary_query: str
    query_plan: dict[str, Any]
    retrieval_config: dict[str, Any]
    retrieval_run_id: uuid.UUID | None
    candidate_count: int
    selected_evidence_count: int
    coverage_score: float
    coverage_state: str
    coverage_summary: dict[str, Any] | None
    warnings: list[Any] | None
    error_message: str | None
    duration_ms: int | None
    created_at: datetime
    completed_at: datetime | None


class SectionResearchCurrentRead(BaseModel):
    model_config = ConfigDict(extra="forbid")
    run: SectionResearchRunRead
    evidence: list[EvidenceItemRead]
    coverage: CoverageSummaryRead | None


class SectionResearchGenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    force: bool = False
    async_: bool = Field(default=True, alias="async")


class SectionResearchGenerateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: str
    job_id: uuid.UUID | None = None
    run_id: uuid.UUID | None = None
    context_hash: str | None = None
    contract_hash: str | None = None
    evidence_count: int | None = None
    coverage_score: float | None = None
    coverage_state: str | None = None


class SectionResearchRunListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[SectionResearchRunRead]
    total: int
    limit: int
    offset: int


class SectionResearchValidationRead(BaseModel):
    model_config = ConfigDict(extra="forbid")
    validation_status: str
    validation_errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
