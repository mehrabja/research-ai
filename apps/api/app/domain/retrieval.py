"""Domain-owned retrieval contracts and RRF fusion."""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Literal

RetrievalMode = Literal["semantic", "lexical", "hybrid"]
RetrievalAlgorithm = Literal["exact", "ann"]

RETRIEVAL_ALGORITHM_VERSION: str = "m9.1"


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: uuid.UUID
    source_id: uuid.UUID
    report_id: uuid.UUID
    chunk_index: int
    content: str
    char_start: int | None
    char_end: int | None
    page_number: int | None

    vector_distance: float | None
    vector_similarity: float | None
    lexical_score: float | None

    vector_rank: int | None
    lexical_rank: int | None
    fusion_score: float
    final_rank: int

    def evidence_id(self) -> str:
        return f"source:{self.source_id}:chunk:{self.chunk_id}"


def reciprocal_rank_fusion_score(
    *,
    vector_rank: int | None,
    lexical_rank: int | None,
    rrf_k: int,
    vector_weight: float,
    lexical_weight: float,
) -> float:
    if rrf_k <= 0:
        raise ValueError("rrf_k must be > 0")
    if vector_weight < 0 or lexical_weight < 0:
        raise ValueError("weights must be >= 0")
    if vector_weight + lexical_weight <= 0:
        raise ValueError("at least one weight must be > 0")

    score = 0.0
    if vector_rank is not None and vector_rank >= 1:
        score += vector_weight * (1.0 / (rrf_k + vector_rank))
    if lexical_rank is not None and lexical_rank >= 1:
        score += lexical_weight * (1.0 / (rrf_k + lexical_rank))
    return score


__all__ = [
    "RETRIEVAL_ALGORITHM_VERSION",
    "RetrievalAlgorithm",
    "RetrievalMode",
    "RetrievedChunk",
    "reciprocal_rank_fusion_score",
]
