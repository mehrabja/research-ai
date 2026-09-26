"""Hybrid retrieval: semantic + lexical + RRF.

Mode-dependent readiness
------------------------
* semantic / hybrid: require current-profile embeddings.
* lexical:          no embeddings required.

Exact vs ANN
------------
* ann:    ``SET LOCAL hnsw.*``, optionally iterative scan.
* exact:  ``SET LOCAL enable_indexscan=off`` forces sequential scan.
"""
from __future__ import annotations

import functools
import logging
import uuid

from sqlalchemy import bindparam, select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import (
    EmbeddingsNotReadyError,
    RetrievalConfigurationError,
)
from app.db.models.source import Chunk, Source
from app.domain.embeddings import (
    EmbeddingProfile,
    build_embedding_profile_id,
)
from app.domain.retrieval import (
    RetrievalAlgorithm,
    RetrievalMode,
    RetrievedChunk,
    reciprocal_rank_fusion_score,
)
from app.integrations.embeddings.base import EmbeddingProvider
from app.services.reports import get_report

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# pgvector extension version detection
# ---------------------------------------------------------------------------
@functools.lru_cache(maxsize=1)
def _pgvector_extension_version() -> tuple[int, int, int] | None:
    """Parse the pgvector extension version.

    Cached per process. Returns ``None`` if the extension is missing
    or the version string is unparseable.
    """
    from app.db.session import engine

    try:
        with engine.connect() as conn:
            raw = conn.execute(
                text(
                    "SELECT extversion FROM pg_extension "
                    "WHERE extname = 'vector'"
                )
            ).scalar()
    except Exception:
        return None
    if not raw:
        return None
    parts = raw.split(".")
    try:
        nums = [
            int("".join(c for c in p if c.isdigit()) or 0)
            for p in parts
        ]
        while len(nums) < 3:
            nums.append(0)
        return (nums[0], nums[1], nums[2])
    except Exception:
        return None


def _supports_iterative_scan() -> bool:
    v = _pgvector_extension_version()
    return v is not None and v >= (0, 8, 0)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def retrieve(
    db: Session,
    *,
    user_id: uuid.UUID,
    report_id: uuid.UUID,
    query: str,
    top_k: int,
    mode: RetrievalMode,
    algorithm: RetrievalAlgorithm,
    source_ids: list[uuid.UUID] | None,
    provider: EmbeddingProvider,
    profile: EmbeddingProfile,
) -> tuple[list[RetrievedChunk], dict[str, int]]:
    get_report(db, user_id=user_id, report_id=report_id)

    settings = get_settings()
    if top_k < 1 or top_k > settings.embedding_retrieval_top_k_max:
        raise RetrievalConfigurationError("top_k out of bounds")

    eligible_sources = _resolve_sources(
        db, report_id=report_id, source_ids=source_ids
    )
    if not eligible_sources:
        raise RetrievalConfigurationError("no eligible sources")

    profile_id = build_embedding_profile_id(profile)

    coverage = _read_coverage(
        db,
        report_id=report_id,
        source_ids=eligible_sources,
        profile_id=profile_id,
        profile=profile,
    )
    total = coverage["total_chunks"]
    embedded = coverage["embedded_chunks"]

    if total == 0:
        raise EmbeddingsNotReadyError("no chunks in requested scope")

    if mode in ("semantic", "hybrid") and embedded == 0:
        raise EmbeddingsNotReadyError(
            "no current-profile embeddings in requested scope"
        )

    candidate_k = min(
        top_k * settings.embedding_retrieval_candidate_multiplier,
        settings.embedding_retrieval_top_k_max
        * settings.embedding_retrieval_candidate_multiplier,
    )

    vector_candidates: list[tuple[Chunk, float]] = []
    lexical_candidates: list[tuple[Chunk, float]] = []

    if mode in ("semantic", "hybrid"):
        query_vec = provider.embed_query(query)
        vector_candidates = _vector_search(
            db,
            report_ids=[report_id],
            source_ids=eligible_sources,
            query_vec=query_vec,
            limit=candidate_k,
            algorithm=algorithm,
            profile_id=profile_id,
            profile=profile,
        )

    if mode in ("lexical", "hybrid"):
        lexical_candidates = _lexical_search(
            db,
            report_ids=[report_id],
            source_ids=eligible_sources,
            query=query,
            limit=candidate_k,
        )

    source_to_report = dict.fromkeys(eligible_sources, report_id)
    fused = _fuse(
        source_to_report=source_to_report,
        vector_candidates=vector_candidates,
        lexical_candidates=lexical_candidates,
        rrf_k=settings.embedding_rrf_k,
        vector_weight=settings.embedding_vector_weight,
        lexical_weight=settings.embedding_lexical_weight,
        top_k=top_k,
    )
    return fused, coverage


# ---------------------------------------------------------------------------
# Coverage
# ---------------------------------------------------------------------------
def _read_coverage(
    db: Session,
    *,
    report_id: uuid.UUID,
    source_ids: list[uuid.UUID],
    profile_id: str,
    profile: EmbeddingProfile,
) -> dict[str, int]:
    rows = db.execute(
        select(
            Chunk.embedding_status,
            Chunk.embedding_model_version,
            Chunk.embedding_provider,
            Chunk.embedding_dimensions,
            Chunk.embedding.is_not(None),
        )
        .join(Source, Chunk.source_id == Source.id)
        .where(
            Source.report_id == report_id,
            Source.id.in_(source_ids),
        )
    ).all()

    total = len(rows)
    embedded = 0
    pending = 0
    failed = 0
    stale = 0
    for status, model_version, provider, dims, has_emb in rows:
        current = (
            has_emb
            and status == "completed"
            and model_version == profile_id
            and provider == profile.provider
            and dims == profile.dimensions
        )
        if current:
            embedded += 1
            continue
        if status == "failed":
            failed += 1
            continue
        if has_emb and status == "completed":
            stale += 1
            continue
        pending += 1

    return {
        "total_chunks": total,
        "embedded_chunks": embedded,
        "pending_chunks": pending,
        "failed_chunks": failed,
        "stale_chunks": stale,
    }


# ---------------------------------------------------------------------------
# Source filter
# ---------------------------------------------------------------------------
def _resolve_sources(
    db: Session,
    *,
    report_id: uuid.UUID,
    source_ids: list[uuid.UUID] | None,
) -> list[uuid.UUID]:
    stmt = select(Source.id).where(Source.report_id == report_id)
    if source_ids:
        stmt = stmt.where(Source.id.in_(source_ids))
    rows = list(db.execute(stmt).scalars().all())
    if source_ids and set(rows) != set(source_ids):
        raise RetrievalConfigurationError(
            "one or more source_ids do not belong to the report"
        )
    return rows


# ---------------------------------------------------------------------------
# Semantic search
# ---------------------------------------------------------------------------
def _vector_search(
    db: Session,
    *,
    report_ids: list[uuid.UUID],
    source_ids: list[uuid.UUID],
    query_vec: list[float],
    limit: int,
    algorithm: RetrievalAlgorithm,
    profile_id: str,
    profile: EmbeddingProfile,
) -> list[tuple[Chunk, float]]:
    settings = get_settings()

    if algorithm == "ann":
        db.execute(
            text(
                f"SET LOCAL hnsw.ef_search = "
                f"{int(settings.embedding_hnsw_ef_search)}"
            )
        )
        mode = settings.embedding_hnsw_iterative_scan
        if mode != "off" and _supports_iterative_scan():
            try:
                db.execute(
                    text(
                        f"SET LOCAL hnsw.iterative_scan = '{mode}'"
                    )
                )
                db.execute(
                    text(
                        f"SET LOCAL hnsw.max_scan_tuples = "
                        f"{int(settings.embedding_hnsw_max_scan_tuples)}"
                    )
                )
                db.execute(
                    text(
                        f"SET LOCAL hnsw.scan_mem_multiplier = "
                        f"{float(settings.embedding_hnsw_scan_mem_multiplier)}"
                    )
                )
            except Exception:
                logger.warning(
                    "hnsw_iterative_scan_unsupported fallback_to_off"
                )
    else:
        db.execute(text("SET LOCAL enable_indexscan = off"))
        db.execute(text("SET LOCAL enable_bitmapscan = off"))

    distance = Chunk.embedding.cosine_distance(query_vec)

    stmt = (
        select(Chunk, distance.label("distance"))
        .join(Source, Chunk.source_id == Source.id)
        .where(
            Source.report_id.in_(report_ids),
            Source.id.in_(source_ids),
            Chunk.embedding.is_not(None),
            Chunk.embedding_status == "completed",
            Chunk.embedding_model_version == profile_id,
            Chunk.embedding_provider == profile.provider,
            Chunk.embedding_dimensions == profile.dimensions,
        )
        .order_by(distance.asc(), Chunk.id.asc())
        .limit(limit)
    )
    rows = db.execute(stmt).all()
    return [(row[0], float(row[1])) for row in rows]

# ---------------------------------------------------------------------------
# Lexical search
# ---------------------------------------------------------------------------
def _lexical_search(
    db: Session,
    *,
    report_ids: list[uuid.UUID],
    source_ids: list[uuid.UUID],
    query: str,
    limit: int,
) -> list[tuple[Chunk, float]]:
    sql = text(
        """
        SELECT c.id,
               ts_rank_cd(
                   to_tsvector('simple', c.content),
                   websearch_to_tsquery('simple', :q)
               ) AS score
        FROM chunks c
        JOIN sources s ON s.id = c.source_id
        WHERE s.report_id = ANY(:report_ids)
          AND s.id IN :source_ids
          AND to_tsvector('simple', c.content)
              @@ websearch_to_tsquery('simple', :q)
        ORDER BY score DESC, c.id ASC
        LIMIT :limit
        """
    ).bindparams(bindparam("source_ids", expanding=True))

    rows = db.execute(
        sql,
        {
            "q": query,
            "report_ids": report_ids,
            "source_ids": source_ids,
            "limit": limit,
        },
    ).all()
    if not rows:
        return []

    chunk_ids = [row[0] for row in rows]
    chunks = {
        c.id: c
        for c in db.execute(
            select(Chunk).where(Chunk.id.in_(chunk_ids))
        ).scalars().all()
    }
    result: list[tuple[Chunk, float]] = []
    for cid, score in rows:
        chunk = chunks.get(cid)
        if chunk is not None:
            result.append((chunk, float(score)))
    return result

# ---------------------------------------------------------------------------
# Fusion
# ---------------------------------------------------------------------------
def _fuse(
    *,
    source_to_report: dict[uuid.UUID, uuid.UUID],
    vector_candidates: list[tuple[Chunk, float]],
    lexical_candidates: list[tuple[Chunk, float]],
    rrf_k: int,
    vector_weight: float,
    lexical_weight: float,
    top_k: int,
) -> list[RetrievedChunk]:
    vector_rank = {
        c.id: i + 1 for i, (c, _) in enumerate(vector_candidates)
    }
    lexical_rank = {
        c.id: i + 1 for i, (c, _) in enumerate(lexical_candidates)
    }
    vector_dist = {c.id: d for c, d in vector_candidates}
    lexical_score = {c.id: s for c, s in lexical_candidates}

    all_ids = set(vector_rank) | set(lexical_rank)
    chunks_by_id: dict[uuid.UUID, Chunk] = {}
    for c, _ in vector_candidates + lexical_candidates:
        chunks_by_id[c.id] = c

    scored: list[tuple[float, uuid.UUID]] = []
    for cid in all_ids:
        score = reciprocal_rank_fusion_score(
            vector_rank=vector_rank.get(cid),
            lexical_rank=lexical_rank.get(cid),
            rrf_k=rrf_k,
            vector_weight=vector_weight,
            lexical_weight=lexical_weight,
        )
        scored.append((score, cid))

    scored.sort(key=lambda t: (-t[0], str(t[1])))
    scored = scored[:top_k]

    results: list[RetrievedChunk] = []
    for rank, (score, cid) in enumerate(scored, start=1):
        chunk = chunks_by_id[cid]
        dist = vector_dist.get(cid)
        report_id = source_to_report.get(chunk.source_id)
        if report_id is None:
            continue
        results.append(
            RetrievedChunk(
                chunk_id=chunk.id,
                source_id=chunk.source_id,
                report_id=report_id,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                char_start=chunk.char_start,
                char_end=chunk.char_end,
                page_number=chunk.page_number,
                vector_distance=dist,
                vector_similarity=(
                    1.0 - dist if dist is not None else None
                ),
                lexical_score=lexical_score.get(cid),
                vector_rank=vector_rank.get(cid),
                lexical_rank=lexical_rank.get(cid),
                fusion_score=score,
                final_rank=rank,
            )
        )
    return results

def _resolve_project_sources(
    db: Session,
    *,
    project_id: uuid.UUID,
    source_ids: list[uuid.UUID] | None,
) -> tuple[list[uuid.UUID], list[uuid.UUID]]:
    from app.db.models.report import Report

    report_ids = list(db.execute(
        select(Report.id).where(Report.project_id == project_id)
    ).scalars().all())
    if not report_ids:
        return [], []

    stmt = select(Source.id).where(Source.report_id.in_(report_ids))
    if source_ids:
        stmt = stmt.where(Source.id.in_(source_ids))
    rows = list(db.execute(stmt).scalars().all())
    if source_ids and set(rows) != set(source_ids):
        raise RetrievalConfigurationError(
            "one or more source_ids do not belong to the project"
        )
    return report_ids, rows


def _read_coverage_multi(
    db: Session,
    *,
    report_ids: list[uuid.UUID],
    source_ids: list[uuid.UUID],
    profile_id: str,
    profile: EmbeddingProfile,
) -> dict[str, int]:
    rows = db.execute(
        select(
            Chunk.embedding_status,
            Chunk.embedding_model_version,
            Chunk.embedding_provider,
            Chunk.embedding_dimensions,
            Chunk.embedding.is_not(None),
        )
        .join(Source, Chunk.source_id == Source.id)
        .where(
            Source.report_id.in_(report_ids),
            Source.id.in_(source_ids),
        )
    ).all()
    total = len(rows)
    embedded = 0
    pending = 0
    failed = 0
    stale = 0
    for status, mv, prov, dims, has_emb in rows:
        current = (
            has_emb
            and status == "completed"
            and mv == profile_id
            and prov == profile.provider
            and dims == profile.dimensions
        )
        if current:
            embedded += 1
            continue
        if status == "failed":
            failed += 1
            continue
        if has_emb and status == "completed":
            stale += 1
            continue
        pending += 1
    return {
        "total_chunks": total,
        "embedded_chunks": embedded,
        "pending_chunks": pending,
        "failed_chunks": failed,
        "stale_chunks": stale,
    }


def retrieve_project_scope(
    db: Session,
    *,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
    query: str,
    top_k: int,
    mode: RetrievalMode,
    algorithm: RetrievalAlgorithm,
    source_ids: list[uuid.UUID] | None,
    provider: EmbeddingProvider,
    profile: EmbeddingProfile,
) -> tuple[list[RetrievedChunk], dict[str, int]]:
    """Project-scoped hybrid retrieval.

    Same algorithm as ``retrieve()`` but the corpus spans every report
    in the project. Used by M26.
    """
    from app.services.projects import get_project

    get_project(db, user_id=user_id, project_id=project_id)

    settings = get_settings()
    if top_k < 1 or top_k > settings.embedding_retrieval_top_k_max:
        raise RetrievalConfigurationError("top_k out of bounds")

    report_ids, eligible_sources = _resolve_project_sources(
        db, project_id=project_id, source_ids=source_ids
    )
    if not eligible_sources:
        raise RetrievalConfigurationError("no eligible sources")

    profile_id = build_embedding_profile_id(profile)

    coverage = _read_coverage_multi(
        db,
        report_ids=report_ids,
        source_ids=eligible_sources,
        profile_id=profile_id,
        profile=profile,
    )
    total = coverage["total_chunks"]
    embedded = coverage["embedded_chunks"]

    if total == 0:
        raise EmbeddingsNotReadyError("no chunks in requested scope")
    if mode in ("semantic", "hybrid") and embedded == 0:
        raise EmbeddingsNotReadyError(
            "no current-profile embeddings in requested scope"
        )

    candidate_k = min(
        top_k * settings.embedding_retrieval_candidate_multiplier,
        settings.embedding_retrieval_top_k_max
        * settings.embedding_retrieval_candidate_multiplier,
    )

    vector_candidates: list[tuple[Chunk, float]] = []
    lexical_candidates: list[tuple[Chunk, float]] = []

    if mode in ("semantic", "hybrid"):
        query_vec = provider.embed_query(query)
        vector_candidates = _vector_search(
            db,
            report_ids=report_ids,
            source_ids=eligible_sources,
            query_vec=query_vec,
            limit=candidate_k,
            algorithm=algorithm,
            profile_id=profile_id,
            profile=profile,
        )

    if mode in ("lexical", "hybrid"):
        lexical_candidates = _lexical_search(
            db,
            report_ids=report_ids,
            source_ids=eligible_sources,
            query=query,
            limit=candidate_k,
        )

    source_to_report: dict[uuid.UUID, uuid.UUID] = dict(
        db.execute(
            select(Source.id, Source.report_id).where(
                Source.id.in_(eligible_sources)
            )
        ).tuples().all()
    )

    fused = _fuse(
        source_to_report=source_to_report,
        vector_candidates=vector_candidates,
        lexical_candidates=lexical_candidates,
        rrf_k=settings.embedding_rrf_k,
        vector_weight=settings.embedding_vector_weight,
        lexical_weight=settings.embedding_lexical_weight,
        top_k=top_k,
    )
    return fused, coverage

__all__ = ["retrieve", "retrieve_project_scope"]
