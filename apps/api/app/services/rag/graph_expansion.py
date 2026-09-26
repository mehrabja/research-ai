"""M26 — Graph-aware candidate expansion via M25."""
from __future__ import annotations

import logging
import uuid

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.exceptions import KnowledgeGraphNotFound
from app.db.models.knowledge_graph import KnowledgeGraphNode
from app.db.models.source import Source
from app.services.knowledge_graph import queries as kg_queries
from app.services.rag.candidates import Candidate

logger = logging.getLogger(__name__)

_MATERIALIZABLE_NODE_TYPES = {"source"}


def _resolve_source_entities(
    db: Session,
    *,
    project_id: uuid.UUID,
    entity_ids: set[uuid.UUID],
) -> set[uuid.UUID]:
    if not entity_ids:
        return set()
    from app.db.models.report import Report

    rows = db.execute(
        select(Source.id)
        .join(Report, Source.report_id == Report.id)
        .where(
            Source.id.in_(list(entity_ids)),
            Report.project_id == project_id,
        )
    ).scalars().all()
    return set(rows)


def _chunks_for_sources_balanced(
    db: Session,
    *,
    source_ids: set[uuid.UUID],
    max_chunks: int,
) -> list[tuple[uuid.UUID, uuid.UUID, int]]:
    if not source_ids or max_chunks <= 0:
        return []

    ids = list(source_ids)
    per_source_cap = max(1, max_chunks // max(1, len(ids)))

    sql = text(
        """
        SELECT chunk_id, source_id, chunk_index
        FROM (
            SELECT c.id AS chunk_id,
                   c.source_id AS source_id,
                   c.chunk_index AS chunk_index,
                   row_number() OVER (
                       PARTITION BY c.source_id
                       ORDER BY c.chunk_index ASC, c.id ASC
                   ) AS rn
            FROM chunks c
            WHERE c.source_id = ANY(:source_ids)
        ) ranked
        WHERE rn <= :cap
        ORDER BY source_id ASC, chunk_index ASC, chunk_id ASC
        LIMIT :limit
        """
    )
    rows = db.execute(
        sql,
        {
            "source_ids": ids,
            "cap": per_source_cap,
            "limit": max_chunks,
        },
    ).all()
    return [(r[0], r[1], int(r[2])) for r in rows]


def _source_to_report(
    db: Session, *, source_ids: set[uuid.UUID]
) -> dict[uuid.UUID, uuid.UUID]:
    if not source_ids:
        return {}
    rows = db.execute(
        select(Source.id, Source.report_id).where(
            Source.id.in_(list(source_ids))
        )
    ).all()
    return {r[0]: r[1] for r in rows}


def expand_candidates(
    db: Session,
    *,
    project_id: uuid.UUID,
    graph_version_id: uuid.UUID | None,
    seed_candidates: list[Candidate],
    max_depth: int,
    max_nodes: int,
) -> tuple[list[Candidate], list[str]]:
    warnings: list[str] = []
    if graph_version_id is None or not seed_candidates:
        return seed_candidates, warnings

    seed_source_ids = {c.source_id for c in seed_candidates}

    rows = db.execute(
        select(KnowledgeGraphNode).where(
            KnowledgeGraphNode.graph_version_id == graph_version_id,
            KnowledgeGraphNode.entity_id.in_(list(seed_source_ids)),
            KnowledgeGraphNode.node_type == "source",
        )
    ).scalars().all()
    node_by_entity = {n.entity_id: n for n in rows}

    seen = {(c.chunk_id, c.source_id) for c in seed_candidates}
    candidate_source_ids: set[uuid.UUID] = set()
    depth_by_source: dict[uuid.UUID, int] = {}
    skipped_by_type: dict[str, int] = {}

    for c in seed_candidates:
        node = node_by_entity.get(c.source_id)
        if node is None:
            continue
        try:
            result = kg_queries.bounded_traversal(
                db,
                project_id=project_id,
                start_node_id=node.id,
                max_depth=max_depth,
                max_nodes=max_nodes,
            )
        except KnowledgeGraphNotFound as exc:
            warnings.append(f"graph_unavailable: {exc}")
            continue

        for n in result.get("nodes", []):
            if n["id"] == node.id:
                continue
            ntype = n["node_type"]
            if ntype not in _MATERIALIZABLE_NODE_TYPES:
                skipped_by_type[ntype] = (
                    skipped_by_type.get(ntype, 0) + 1
                )
                continue
            entity_id = n["entity_id"]
            depth = int(n.get("depth", 1))
            prev = depth_by_source.get(entity_id)
            if prev is None or depth < prev:
                depth_by_source[entity_id] = depth
            candidate_source_ids.add(entity_id)

    resolved = _resolve_source_entities(
        db, project_id=project_id, entity_ids=candidate_source_ids
    )
    dropped = len(candidate_source_ids) - len(resolved)
    if dropped:
        warnings.append(f"graph_unresolved_sources_dropped: {dropped}")

    chunk_rows = _chunks_for_sources_balanced(
        db, source_ids=resolved, max_chunks=max_nodes
    )
    src_to_report = _source_to_report(db, source_ids=resolved)

    expansions: list[Candidate] = []
    for chunk_id, source_id, chunk_index in chunk_rows:
        key = (chunk_id, source_id)
        if key in seen:
            continue
        seen.add(key)
        report_id = src_to_report.get(source_id)
        if report_id is None:
            continue
        depth = depth_by_source.get(source_id, 1)
        expansions.append(Candidate(
            chunk_id=chunk_id,
            source_id=source_id,
            report_id=report_id,
            chunk_index=chunk_index,
            vector_distance=None,
            vector_rank=None,
            lexical_score=None,
            lexical_rank=None,
            fusion_score=0.0,
            stage=f"graph:d{depth}",
        ))

    if skipped_by_type:
        total_skipped = sum(skipped_by_type.values())
        warnings.append(
            f"graph_nodes_skipped_non_materializable: {total_skipped} "
            f"({', '.join(f'{k}={v}' for k, v in sorted(skipped_by_type.items()))})"
        )

    return seed_candidates + expansions, warnings


__all__ = ["expand_candidates"]
