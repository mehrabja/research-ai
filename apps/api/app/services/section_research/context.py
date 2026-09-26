"""M28 — Deterministic section-research context hash."""
from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

from app.domain.embeddings import (
    EmbeddingProfile,
    build_embedding_profile_id,
)
from app.domain.retrieval_advanced import (
    ADVANCED_RAG_VERSION,
    GRAPH_EXPANSION_VERSION,
    QUERY_DECOMPOSITION_VERSION,
    RANKING_MODEL_VERSION,
)
from app.domain.section_research import (
    SECTION_RESEARCH_CONTEXT_VERSION,
    SECTION_RESEARCH_QUERY_VERSION,
    SECTION_RESEARCH_VERSION,
)


def _json(v: Any) -> str:
    return json.dumps(
        v, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )


def _sha256(parts: list[str]) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(p.encode("utf-8"))
        h.update(b"\x00")
    return h.hexdigest()[:32]


def compute_section_research_context_hash(
    *,
    project_id: uuid.UUID,
    report_id: uuid.UUID,
    manuscript_version_id: uuid.UUID,
    manuscript_section_id: uuid.UUID,
    contract_hash: str,
    profile: EmbeddingProfile,
    mode: str,
    algorithm: str,
    effective_filters: dict[str, Any],
    effective_max_results: int,
    candidate_limit: int,
    query_plan_version: str = SECTION_RESEARCH_QUERY_VERSION,
) -> str:
    profile_id = build_embedding_profile_id(profile)
    parts: list[str] = [
        f"m28:{SECTION_RESEARCH_VERSION}",
        f"query:{query_plan_version}",
        f"ctx:{SECTION_RESEARCH_CONTEXT_VERSION}",
        f"m26_rag:{ADVANCED_RAG_VERSION}",
        f"m26_decomp:{QUERY_DECOMPOSITION_VERSION}",
        f"m26_graph:{GRAPH_EXPANSION_VERSION}",
        f"m26_rank:{RANKING_MODEL_VERSION}",
        f"project:{project_id}",
        f"report:{report_id}",
        f"version:{manuscript_version_id}",
        f"section:{manuscript_section_id}",
        f"contract:{contract_hash}",
        f"profile:{profile_id}",
        f"mode:{mode}",
        f"algorithm:{algorithm}",
        "filters:" + _json(effective_filters),
        f"max_results:{int(effective_max_results)}",
        f"candidate_limit:{int(candidate_limit)}",
    ]
    return _sha256(parts)


__all__ = ["compute_section_research_context_hash"]
