"""M26 — Candidate generation via M09/M11 hybrid retrieval."""
from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.domain.embeddings import EmbeddingProfile
from app.domain.retrieval import (
    RetrievalAlgorithm,
    RetrievalMode,
    RetrievedChunk,
)
from app.integrations.embeddings.base import EmbeddingProvider
from app.services import retrieval as retrieval_svc


@dataclass(frozen=True)
class Candidate:
    chunk_id: uuid.UUID
    source_id: uuid.UUID
    report_id: uuid.UUID
    chunk_index: int
    vector_distance: float | None
    vector_rank: int | None
    lexical_score: float | None
    lexical_rank: int | None
    fusion_score: float
    stage: str


def _to_candidate(rc: RetrievedChunk) -> Candidate:
    return Candidate(
        chunk_id=rc.chunk_id,
        source_id=rc.source_id,
        report_id=rc.report_id,
        chunk_index=rc.chunk_index,
        vector_distance=rc.vector_distance,
        vector_rank=rc.vector_rank,
        lexical_score=rc.lexical_score,
        lexical_rank=rc.lexical_rank,
        fusion_score=rc.fusion_score,
        stage="hybrid",
    )


def generate_candidates(
    db: Session,
    *,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
    query: str,
    mode: RetrievalMode,
    algorithm: RetrievalAlgorithm,
    limit: int,
    allowed_source_ids: list[uuid.UUID] | None,
    provider: EmbeddingProvider,
    profile: EmbeddingProfile,
) -> tuple[list[Candidate], dict[str, int], list[str]]:
    chunks, coverage = retrieval_svc.retrieve_project_scope(
        db,
        user_id=user_id,
        project_id=project_id,
        query=query,
        top_k=limit,
        mode=mode,
        algorithm=algorithm,
        source_ids=allowed_source_ids,
        provider=provider,
        profile=profile,
    )
    return [_to_candidate(c) for c in chunks], coverage, []


__all__ = ["Candidate", "generate_candidates"]
