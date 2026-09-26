"""M26 — Complete, deterministic retrieval context hash.

Identity includes: corpus state, embedding profile, retrieval
versions, effective request configuration, LLM feature flags, and
generation provider/model identity. No secrets are ever included.
"""
from __future__ import annotations

import hashlib
import json
import uuid

from sqlalchemy import func, select
from sqlalchemy import text as _text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models.report import Report
from app.db.models.source import Chunk, Source
from app.domain.embeddings import (
    EmbeddingProfile,
    build_embedding_profile_id,
)
from app.domain.retrieval_advanced import (
    ADVANCED_RAG_VERSION,
    GRAPH_EXPANSION_VERSION,
    QUERY_DECOMPOSITION_VERSION,
    RANKING_MODEL_VERSION,
    RESEARCH_MEMORY_VERSION,
)
from app.services.knowledge_graph import context as kg_ctx
from app.services.rag.coverage import INTENT_COVERAGE_VERSION
from app.services.rag.graph_context import GRAPH_CONTEXT_VERSION
from app.services.rag.llm_decomposition import (
    LLM_DECOMPOSITION_VERSION,
)
from app.services.rag.llm_rerank import LLM_RERANK_VERSION


def _sha256(parts: list[str]) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(p.encode("utf-8"))
        h.update(b"\x00")
    return h.hexdigest()[:32]


def _corpus_hash(db: Session, *, project_id: uuid.UUID) -> str:
    src_row = db.execute(
        select(
            func.count(func.distinct(Source.id)),
            func.max(Source.updated_at),
        )
        .join(Report, Source.report_id == Report.id)
        .where(Report.project_id == project_id)
    ).one()
    source_count, source_updated = src_row

    chunk_row = db.execute(
        select(
            func.count(Chunk.id),
            func.coalesce(func.sum(Chunk.char_end), 0),
            func.max(Chunk.created_at),
            func.max(Chunk.embedding_started_at),
            func.max(Chunk.embedding_completed_at),
        )
        .join(Source, Chunk.source_id == Source.id)
        .join(Report, Source.report_id == Report.id)
        .where(Report.project_id == project_id)
    ).one()
    (
        chunk_count,
        char_sum,
        last_chunk_created,
        last_emb_started,
        last_emb_completed,
    ) = chunk_row

    content_fp = db.execute(
        _text(
            """
            SELECT md5(string_agg(
                c.id::text || ':' || md5(c.content),
                ',' ORDER BY c.id
            ))
            FROM chunks c
            JOIN sources s ON s.id = c.source_id
            JOIN reports r ON r.id = s.report_id
            WHERE r.project_id = :pid
            """
        ),
        {"pid": project_id},
    ).scalar()
    if content_fp is None:
        content_fp = "-"

    status_rows = db.execute(
        select(Chunk.embedding_status, func.count(Chunk.id))
        .join(Source, Chunk.source_id == Source.id)
        .join(Report, Source.report_id == Report.id)
        .where(Report.project_id == project_id)
        .group_by(Chunk.embedding_status)
    ).all()
    status_sig = ",".join(
        f"{s or 'null'}={int(c)}" for s, c in sorted(
            status_rows, key=lambda x: (x[0] or "")
        )
    )

    return _sha256([
        f"src_count:{int(source_count or 0)}",
        f"src_updated:{source_updated.isoformat() if source_updated else '-'}",
        f"chunk_count:{int(chunk_count or 0)}",
        f"chars:{int(char_sum or 0)}",
        f"chunk_created:{last_chunk_created.isoformat() if last_chunk_created else '-'}",
        f"emb_started:{last_emb_started.isoformat() if last_emb_started else '-'}",
        f"emb_completed:{last_emb_completed.isoformat() if last_emb_completed else '-'}",
        f"content_fp:{content_fp}",
        f"status:{status_sig}",
    ])


def _provider_identity(
    *,
    llm_decomposition_enabled: bool,
    llm_rerank_enabled: bool,
) -> str:
    """Non-sensitive provider/model identity for cache isolation.

    Only included when at least one LLM feature is active. Never
    contains API keys, tokens, or secrets.
    """
    if not (llm_decomposition_enabled or llm_rerank_enabled):
        return "llm_provider:none"
    from app.services.generation_profile import (
        get_current_generation_profile,
        get_current_generation_profile_id,
    )

    profile = get_current_generation_profile()
    return (
        "llm_provider:"
        f"name={profile.provider}|"
        f"model={profile.model}|"
        f"version={get_current_generation_profile_id()}"
    )


def compute_retrieval_context_hash(
    db: Session,
    *,
    project_id: uuid.UUID,
    report_id: uuid.UUID | None,
    query_hash: str,
    graph_version_id: uuid.UUID | None,
    plan_id: uuid.UUID | None,
    section_id: uuid.UUID | None,
    requirement_id: uuid.UUID | None,
    mode: str,
    algorithm: str,
    filters: dict,
    profile: EmbeddingProfile,
    effective_graph_enabled: bool,
    effective_memory_enabled: bool,
    effective_diversity_enabled: bool,
    effective_max_results: int,
    candidate_limit: int,
) -> str:
    settings = get_settings()
    profile_id = build_embedding_profile_id(profile)

    parts: list[str] = [
        f"rag:{ADVANCED_RAG_VERSION}",
        f"decomp:{QUERY_DECOMPOSITION_VERSION}",
        f"graph:{GRAPH_EXPANSION_VERSION}",
        f"ranking:{RANKING_MODEL_VERSION}",
        f"memory:{RESEARCH_MEMORY_VERSION}",
        f"coverage:{INTENT_COVERAGE_VERSION}",
        f"graph_ctx:{GRAPH_CONTEXT_VERSION}",
        f"llm_decomp_ver:{LLM_DECOMPOSITION_VERSION}",
        f"llm_rerank_ver:{LLM_RERANK_VERSION}",
        f"project:{project_id}",
        f"report:{report_id or '-'}",
        f"qhash:{query_hash}",
        f"mode:{mode}",
        f"algo:{algorithm}",
        f"profile:{profile_id}",
        f"gv:{graph_version_id or '-'}",
        f"plan:{plan_id or '-'}",
        f"section:{section_id or '-'}",
        f"req:{requirement_id or '-'}",
        f"filters:{json.dumps(filters, sort_keys=True, default=str)}",
        f"corpus:{_corpus_hash(db, project_id=project_id)}",
        f"eff_graph:{int(effective_graph_enabled)}",
        f"eff_memory:{int(effective_memory_enabled)}",
        f"eff_diversity:{int(effective_diversity_enabled)}",
        f"eff_max_results:{effective_max_results}",
        f"candidate_limit:{candidate_limit}",
        f"mmr_lambda:{settings.rag_mmr_lambda}",
        f"mem_min_imp:{settings.rag_memory_min_importance}",
        f"mem_reuse_top_k:{settings.rag_memory_reuse_top_k}",
        f"max_candidates:{settings.rag_max_candidates}",
        f"max_graph_depth:{settings.rag_max_graph_depth}",
        f"max_graph_nodes:{settings.rag_max_graph_nodes}",
        f"min_relevance:{settings.rag_min_relevance}",
        f"llm_decomp_enabled:{int(settings.rag_llm_decomposition_enabled)}",
        f"llm_rerank_enabled:{int(settings.rag_llm_rerank_enabled)}",
        _provider_identity(
            llm_decomposition_enabled=(
                settings.rag_llm_decomposition_enabled
            ),
            llm_rerank_enabled=settings.rag_llm_rerank_enabled,
        ),
        f"rrf_k:{settings.embedding_rrf_k}",
        f"vec_w:{settings.embedding_vector_weight}",
        f"lex_w:{settings.embedding_lexical_weight}",
    ]

    if graph_version_id is not None:
        gh = kg_ctx.compute_graph_context_hash(
            db, project_id=project_id
        )
        parts.append(f"graph_context:{gh}")
    else:
        parts.append("graph_context:none")

    return _sha256(parts)


__all__ = ["compute_retrieval_context_hash"]
