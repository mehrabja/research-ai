"""M26 — M25 graph context for retrieval coverage.

Deterministic graph context from the active M25 graph version. All
returned source ids are backed by real source nodes in the same
project. Graph-only nodes are never treated as evidence.

Scope:
    Currently project-scoped because the M25 query layer does not
    expose a per-requirement gap filter. When M25 gains that
    capability, add ``requirement_id`` narrowing here and update the
    context hash accordingly.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.knowledge_graph import (
    KnowledgeGraphEdge,
    KnowledgeGraphNode,
)

GRAPH_CONTEXT_VERSION = "m26-graph-ctx-v1"


def _resolve_source_entities(
    db: Session,
    *,
    project_id: uuid.UUID,
    source_node_ids: list[uuid.UUID],
) -> set[uuid.UUID]:
    if not source_node_ids:
        return set()
    rows = db.execute(
        select(KnowledgeGraphNode.entity_id).where(
            KnowledgeGraphNode.id.in_(source_node_ids),
            KnowledgeGraphNode.node_type == "source",
            KnowledgeGraphNode.project_id == project_id,
        )
    ).scalars().all()
    return set(rows)


def load_gap_source_ids(
    db: Session,
    *,
    project_id: uuid.UUID,
    graph_version_id: uuid.UUID,
) -> set[uuid.UUID]:
    """Sources downstream of literature_gap nodes.

    Chain: literature_gap → literature_cluster
           → literature_item → source
    """
    gap_node_ids = list(db.execute(
        select(KnowledgeGraphNode.id).where(
            KnowledgeGraphNode.graph_version_id == graph_version_id,
            KnowledgeGraphNode.project_id == project_id,
            KnowledgeGraphNode.node_type == "literature_gap",
        )
    ).scalars().all())
    if not gap_node_ids:
        return set()

    cluster_edges = list(db.execute(
        select(KnowledgeGraphEdge.target_node_id).where(
            KnowledgeGraphEdge.graph_version_id == graph_version_id,
            KnowledgeGraphEdge.source_node_id.in_(gap_node_ids),
            KnowledgeGraphEdge.relation_type
            == "gap_detected_from_cluster",
        )
    ).scalars().all())
    if not cluster_edges:
        return set()

    item_edges = list(db.execute(
        select(KnowledgeGraphEdge.target_node_id).where(
            KnowledgeGraphEdge.graph_version_id == graph_version_id,
            KnowledgeGraphEdge.source_node_id.in_(cluster_edges),
            KnowledgeGraphEdge.relation_type
            == "cluster_contains_literature_item",
        )
    ).scalars().all())
    if not item_edges:
        return set()

    source_edges = list(db.execute(
        select(KnowledgeGraphEdge.target_node_id).where(
            KnowledgeGraphEdge.graph_version_id == graph_version_id,
            KnowledgeGraphEdge.source_node_id.in_(item_edges),
            KnowledgeGraphEdge.relation_type
            == "literature_item_refers_to_source",
        )
    ).scalars().all())
    if not source_edges:
        return set()

    return _resolve_source_entities(
        db,
        project_id=project_id,
        source_node_ids=source_edges,
    )


def build_graph_context(
    db: Session,
    *,
    project_id: uuid.UUID,
    graph_version_id: uuid.UUID | None,
) -> dict | None:
    """Return deterministic graph context for coverage, or None."""
    if graph_version_id is None:
        return None

    gap_source_ids = load_gap_source_ids(
        db,
        project_id=project_id,
        graph_version_id=graph_version_id,
    )
    return {
        "graph_context_version": GRAPH_CONTEXT_VERSION,
        "graph_version_id": str(graph_version_id),
        "gap_source_ids": sorted(str(x) for x in gap_source_ids),
    }


__all__ = [
    "GRAPH_CONTEXT_VERSION",
    "build_graph_context",
    "load_gap_source_ids",
]
