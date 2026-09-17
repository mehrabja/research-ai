"""Retrieval endpoint schemas."""
from __future__ import annotations

import uuid

from pydantic import BaseModel, Field

from app.domain.retrieval import RetrievalMode


class RetrievalRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    top_k: int = Field(default=8, ge=1, le=50)
    mode: RetrievalMode = "hybrid"
    source_ids: list[uuid.UUID] | None = None


class RetrievedChunkResponse(BaseModel):
    evidence_id: str
    source_id: uuid.UUID
    chunk_id: uuid.UUID
    chunk_index: int
    page_number: int | None
    char_start: int | None
    char_end: int | None
    content: str
    vector_similarity: float | None
    lexical_score: float | None
    vector_rank: int | None
    lexical_rank: int | None
    fusion_score: float
    final_rank: int


class RetrievalCoverage(BaseModel):
    total_chunks: int
    embedded_chunks: int
    pending_chunks: int
    failed_chunks: int
    stale_chunks: int


class RetrievalResponse(BaseModel):
    query: str
    mode: RetrievalMode
    profile_id: str
    retrieval_algorithm_version: str
    coverage: RetrievalCoverage
    results: list[RetrievedChunkResponse]
