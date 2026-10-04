"""M26 — Advanced RAG & Research Memory schemas."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

RetrievalModeLiteral = Literal["semantic", "lexical", "hybrid"]


class RetrieveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    query: str = Field(min_length=1, max_length=4000)
    report_id: uuid.UUID | None = None
    plan_section_id: uuid.UUID | None = None
    evidence_requirement_id: uuid.UUID | None = None

    mode: RetrievalModeLiteral | None = None
    algorithm: Literal["exact", "ann"] | None = None
    max_results: int | None = Field(default=None, ge=1, le=200)

    graph_expansion_enabled: bool | None = None
    memory_enabled: bool | None = None
    diversity_enabled: bool | None = None

    min_year: int | None = Field(default=None, ge=1000, le=2200)
    max_year: int | None = Field(default=None, ge=1000, le=2200)
    required_full_text: bool = False
    allowed_source_ids: list[uuid.UUID] | None = None

    async_: bool | None = Field(default=None, alias="async")

class RetrievedChunkRead(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rank: int
    chunk_id: uuid.UUID | None
    source_id: uuid.UUID | None
    final_score: float
    vector_score: float | None
    lexical_score: float | None
    graph_score: float | None
    memory_score: float | None
    quality_score: float | None
    diversity_penalty: float | None
    retrieval_stage: str
    retrieval_reason: list[str]
    graph_distance: int | None
    memory_match: uuid.UUID | None


class CoverageRead(BaseModel):
    model_config = ConfigDict(extra="forbid")
    requested_intents: list[str] = Field(default_factory=list)
    satisfied_intents: list[str] = Field(default_factory=list)
    weak_intents: list[str] = Field(default_factory=list)
    missing_intents: list[str] = Field(default_factory=list)


class RetrievalRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: uuid.UUID
    project_id: uuid.UUID
    query: str
    normalized_query: str
    query_hash: str
    context_hash: str
    retrieval_version: str
    ranking_model_version: str
    status: str
    candidate_count: int
    final_result_count: int
    duration_ms: int | None
    started_at: datetime
    completed_at: datetime | None
    coverage: dict[str, Any] | None
    warnings: list[Any] | None


class RetrieveResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: str
    job_id: uuid.UUID | None = None
    run: RetrievalRunRead | None = None
    results: list[RetrievedChunkRead] = Field(default_factory=list)
    coverage: CoverageRead | None = None
    warnings: list[str] = Field(default_factory=list)

class RetrievalRunListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[RetrievalRunRead] = Field(default_factory=list)
    total: int
    limit: int
    offset: int


class MemoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: uuid.UUID
    project_id: uuid.UUID
    memory_type: str
    status: str
    canonical_entity_type: str | None
    canonical_entity_id: uuid.UUID | None
    summary: str
    importance: float
    confidence: float
    reuse_count: int
    created_at: datetime


class MemoryListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[MemoryRead] = Field(default_factory=list)
    total: int = 0

class RAGReadinessResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: uuid.UUID
    status: str
    saved_sources: int
    processed_sources: int
    embedded_sources: int
    lexical_ready_sources: int
    semantic_ready_sources: int
    reason: str | None = None
