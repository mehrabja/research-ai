"""M23 — Literature intelligence schemas."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class LiteratureItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: uuid.UUID
    project_id: uuid.UUID
    source_id: uuid.UUID

    screening_status: str
    manual_override: bool
    manual_override_at: datetime | None
    manual_override_reason: str | None

    relevance_score: float | None
    relevance_confidence: float | None
    relevance_reason: str | None
    relevance_factors: list[dict[str, Any]] | None

    paper_type_code: str | None
    research_design_code: str | None

    study_summary: str | None
    methods_summary: str | None
    findings_summary: str | None
    limitations_summary: str | None

    population: str | None
    sample_size: int | None
    intervention: str | None
    comparator: str | None
    outcomes: list[str] | None

    themes: list[str] | None
    keywords: list[str] | None
    extraction_provenance: list[dict[str, Any]] | None

    analysis_status: str
    analysis_error: str | None
    analysis_version: str | None

    created_at: datetime
    updated_at: datetime


class LiteratureListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[LiteratureItemRead]
    total: int
    limit: int
    offset: int


class LiteratureScreeningUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    screening_status: str = Field(
        ...,
        pattern="^(discovered|candidate|included|excluded|uncertain)$",
    )
    reason: str | None = Field(default=None, max_length=500)


class LiteratureAnalyzeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    force: bool = False


class LiteratureClusterRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    summary: str | None
    cluster_method: str
    cluster_version: str
    source_count: int
    themes: list[str] | None
    keywords: list[str] | None
    disagreements: list[dict[str, Any]] | None
    limitations: list[str] | None
    representative_source_ids: list[str] | None
    evidence_strength: float | None
    status: str
    created_at: datetime
    updated_at: datetime


class LiteratureClusterListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[LiteratureClusterRead]
    total: int


class LiteratureGapRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: uuid.UUID
    project_id: uuid.UUID
    gap_type: str
    title: str
    description: str
    confidence: float
    supporting_source_ids: list[str] | None
    supporting_cluster_ids: list[str] | None
    evidence_summary: str | None
    status: str
    analysis_version: str
    fingerprint: str | None
    created_at: datetime
    updated_at: datetime


class LiteratureGapListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[LiteratureGapRead]
    total: int


class LiteratureRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: uuid.UUID
    project_id: uuid.UUID
    context_hash: str | None
    analysis_version: str
    status: str
    source_count: int
    included_count: int
    excluded_count: int
    cluster_count: int
    gap_count: int
    duration_ms: int | None
    error_message: str | None
    created_at: datetime


class LiteratureRunListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[LiteratureRunRead]
    total: int
    limit: int
    offset: int


class LiteratureAnalyzeResponse(BaseModel):
    """Unified response for POST /analyze.

    * status="queued": async mode (202), job_id populated, run=None.
    * status in {completed, skipped, failed}: sync mode (200),
      run populated, job_id=None.
    """
    model_config = ConfigDict(extra="forbid")

    status: str
    job_id: uuid.UUID | None = None
    run: LiteratureRunRead | None = None
