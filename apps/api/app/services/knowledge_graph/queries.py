"""M25 — Knowledge graph query layer."""
from __future__ import annotations

import uuid

from sqlalchemy import or_, select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import (
    KnowledgeGraphInvalid,
    KnowledgeGraphNotFound,
)
from app.db.models.knowledge_graph import (
    KnowledgeGraphEdge,
    KnowledgeGraphNode,
    KnowledgeGraphVersion,
)
from app.domain.knowledge_graph import (
    KNOWLEDGE_GRAPH_NODE_TYPES,
    KNOWLEDGE_GRAPH_RELATION_TYPES,
)


def get_active_version(
    db: Session, *, project_id: uuid.UUID
) -> KnowledgeGraphVersion:
    gv = db.execute(
        select(KnowledgeGraphVersion)
        .where(
            KnowledgeGraphVersion.project_id == project_id,
            KnowledgeGraphVersion.status == "ready",
        )
        .order_by(KnowledgeGraphVersion.version.desc())
        .limit(1)
    ).scalar_one_or_none()
    if gv is None:
        raise KnowledgeGraphNotFound()
    return gv


def get_graph(
    db: Session, *, project_id: uuid.UUID
) -> KnowledgeGraphVersion:
    return get_active_version(db, project_id=project_id)


def _validate_relation_types(
    relation_types: list[str] | None,
) -> list[str] | None:
    if not relation_types:
        return None
    allowed = set(KNOWLEDGE_GRAPH_RELATION_TYPES)
    unknown = [r for r in relation_types if r not in allowed]
    if unknown:
        raise KnowledgeGraphInvalid(
            "unknown relation type(s): " + ", ".join(sorted(unknown))
        )
    return relation_types


def get_graph_summary(db: Session, *, project_id: uuid.UUID) -> dict:
    gv = get_active_version(db, project_id=project_id)
    node_counts = db.execute(
        select(KnowledgeGraphNode.node_type, text("count(*)"))
        .where(KnowledgeGraphNode.graph_version_id == gv.id)
        .group_by(KnowledgeGraphNode.node_type)
    ).all()
    edge_counts = db.execute(
        select(KnowledgeGraphEdge.relation_type, text("count(*)"))
        .where(KnowledgeGraphEdge.graph_version_id == gv.id)
        .group_by(KnowledgeGraphEdge.relation_type)
    ).all()
    return {
        "graph_version_id": gv.id,
        "version": gv.version,
        "status": gv.status,
        "node_count": int(gv.node_count),
        "edge_count": int(gv.edge_count),
        "node_type_counts": {str(t): int(c) for t, c in node_counts},
        "relation_type_counts": {str(t): int(c) for t, c in edge_counts},
        "context_hash": gv.context_hash,
        "graph_version": gv.graph_version,
    }


def list_nodes(
    db: Session,
    *,
    project_id: uuid.UUID,
    search: str | None = None,
    node_type: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[KnowledgeGraphNode], int]:
    gv = get_active_version(db, project_id=project_id)
    stmt = select(KnowledgeGraphNode).where(
        KnowledgeGraphNode.graph_version_id == gv.id,
        KnowledgeGraphNode.project_id == project_id,
    )
    if node_type:
        if node_type not in set(KNOWLEDGE_GRAPH_NODE_TYPES):
            raise KnowledgeGraphInvalid("unknown node type: " + node_type)
        stmt = stmt.where(KnowledgeGraphNode.node_type == node_type)
    if search and search.strip():
        pattern = "%" + search.strip() + "%"
        stmt = stmt.where(
            or_(
                KnowledgeGraphNode.node_key.ilike(pattern),
                KnowledgeGraphNode.label.ilike(pattern),
            )
        )
    total = int(
        db.execute(select(text("count(*)")).select_from(stmt.subquery())).scalar_one()
    )
    rows = (
        db.execute(
            stmt.order_by(
                KnowledgeGraphNode.node_type.asc(),
                KnowledgeGraphNode.node_key.asc(),
            )
            .limit(min(limit, 200))
            .offset(offset)
        )
        .scalars()
        .all()
    )
    return list(rows), total


def get_node(
    db: Session, *, project_id: uuid.UUID, node_id: uuid.UUID
) -> KnowledgeGraphNode:
    gv = get_active_version(db, project_id=project_id)
    node = db.execute(
        select(KnowledgeGraphNode).where(
            KnowledgeGraphNode.id == node_id,
            KnowledgeGraphNode.graph_version_id == gv.id,
            KnowledgeGraphNode.project_id == project_id,
        )
    ).scalar_one_or_none()
    if node is None:
        raise KnowledgeGraphNotFound("node not found")
    return node


def get_neighbors(
    db: Session,
    *,
    project_id: uuid.UUID,
    node_id: uuid.UUID,
    relation_types: list[str] | None = None,
    direction: str = "both",
    limit: int | None = None,
) -> list[dict]:
    settings = get_settings()
    gv = get_active_version(db, project_id=project_id)
    rels = _validate_relation_types(relation_types)
    max_nodes = min(
        limit or settings.knowledge_graph_max_nodes,
        settings.knowledge_graph_max_nodes,
    )

    clauses = []
    if direction in ("out", "both"):
        clauses.append(KnowledgeGraphEdge.source_node_id == node_id)
    if direction in ("in", "both"):
        clauses.append(KnowledgeGraphEdge.target_node_id == node_id)
    if not clauses:
        clauses = [KnowledgeGraphEdge.source_node_id == node_id]

    stmt = select(KnowledgeGraphEdge).where(
        KnowledgeGraphEdge.graph_version_id == gv.id,
        or_(*clauses),
    )
    if rels:
        stmt = stmt.where(KnowledgeGraphEdge.relation_type.in_(rels))
    stmt = stmt.limit(max_nodes)
    edges = list(db.execute(stmt).scalars().all())

    neighbor_ids: set[uuid.UUID] = set()
    for e in edges:
        if e.source_node_id != node_id:
            neighbor_ids.add(e.source_node_id)
        if e.target_node_id != node_id:
            neighbor_ids.add(e.target_node_id)
    if not neighbor_ids:
        return []

    nodes = list(db.execute(
        select(KnowledgeGraphNode).where(
            KnowledgeGraphNode.id.in_(list(neighbor_ids)),
            KnowledgeGraphNode.project_id == project_id,
        )
    ).scalars().all())
    node_by_id = {n.id: n for n in nodes}

    results: list[dict] = []
    for e in edges:
        other_id = (
            e.target_node_id if e.source_node_id == node_id
            else e.source_node_id
        )
        n = node_by_id.get(other_id)
        if n is None:
            continue
        results.append({
            "edge_id": e.id,
            "relation_type": e.relation_type,
            "provenance_type": e.provenance_type,
            "provenance_ref": e.provenance_ref,
            "confidence": (
                float(e.confidence) if e.confidence is not None else None
            ),
            "weight": float(e.weight),
            "direction": (
                "out" if e.source_node_id == node_id else "in"
            ),
            "neighbor": {
                "id": n.id,
                "node_type": n.node_type,
                "node_key": n.node_key,
                "entity_id": n.entity_id,
                "label": n.label,
            },
        })
        if len(results) >= max_nodes:
            break
    return results


def bounded_traversal(
    db: Session,
    *,
    project_id: uuid.UUID,
    start_node_id: uuid.UUID,
    max_depth: int | None = None,
    max_nodes: int | None = None,
    relation_types: list[str] | None = None,
) -> dict:
    settings = get_settings()
    depth = min(
        max_depth or settings.knowledge_graph_max_traversal_depth,
        settings.knowledge_graph_max_traversal_depth,
    )
    node_cap = min(
        max_nodes or settings.knowledge_graph_max_nodes,
        settings.knowledge_graph_max_nodes,
    )
    rels = _validate_relation_types(relation_types)
    gv = get_active_version(db, project_id=project_id)

    rel_filter = "AND e.relation_type = ANY(:rels)" if rels else ""

    sql = text(
        f"""
        WITH RECURSIVE walk AS (
            SELECT n.id AS node_id, 0 AS depth, ARRAY[n.id] AS path
            FROM knowledge_graph_nodes n
            WHERE n.id = :start_id
              AND n.graph_version_id = :gv_id
              AND n.project_id = :pid
            UNION ALL
            SELECT
                CASE WHEN e.source_node_id = w.node_id
                     THEN e.target_node_id ELSE e.source_node_id END,
                w.depth + 1,
                w.path || CASE WHEN e.source_node_id = w.node_id
                     THEN e.target_node_id ELSE e.source_node_id END
            FROM walk w
            JOIN knowledge_graph_edges e
              ON (e.source_node_id = w.node_id
                  OR e.target_node_id = w.node_id)
             AND e.graph_version_id = :gv_id
             {rel_filter}
            WHERE w.depth < :max_depth
              AND NOT (CASE WHEN e.source_node_id = w.node_id
                     THEN e.target_node_id ELSE e.source_node_id END
                     = ANY(w.path))
        )
        SELECT DISTINCT node_id, MIN(depth) AS depth
        FROM walk GROUP BY node_id
        ORDER BY depth ASC, node_id ASC LIMIT :cap
        """
    )
    params: dict = {
        "start_id": start_node_id,
        "gv_id": gv.id,
        "pid": project_id,
        "max_depth": depth,
        "cap": node_cap,
    }
    if rels:
        params["rels"] = rels

    rows = db.execute(sql, params).all()
    node_ids = [r[0] for r in rows]
    depth_by_id = {r[0]: int(r[1]) for r in rows}

    nodes: list[dict] = []
    if node_ids:
        fetched = list(db.execute(
            select(KnowledgeGraphNode).where(
                KnowledgeGraphNode.id.in_(node_ids),
                KnowledgeGraphNode.project_id == project_id,
            )
        ).scalars().all())
        for n in fetched:
            nodes.append({
                "id": n.id,
                "node_type": n.node_type,
                "node_key": n.node_key,
                "entity_id": n.entity_id,
                "label": n.label,
                "depth": depth_by_id.get(n.id, 0),
            })

    edge_rows: list = []
    if node_ids:
        edge_stmt = select(KnowledgeGraphEdge).where(
            KnowledgeGraphEdge.graph_version_id == gv.id,
            KnowledgeGraphEdge.source_node_id.in_(node_ids),
            KnowledgeGraphEdge.target_node_id.in_(node_ids),
        )
        if rels:
            edge_stmt = edge_stmt.where(
                KnowledgeGraphEdge.relation_type.in_(rels)
            )
        edge_rows = list(db.execute(edge_stmt).scalars().all())

    edges = [
        {
            "id": e.id,
            "source_node_id": e.source_node_id,
            "target_node_id": e.target_node_id,
            "relation_type": e.relation_type,
            "provenance_type": e.provenance_type,
        }
        for e in edge_rows
    ]
    return {
        "graph_version_id": gv.id,
        "start_node_id": start_node_id,
        "max_depth": depth,
        "max_nodes": node_cap,
        "nodes": nodes,
        "edges": edges,
    }


def find_path(
    db: Session,
    *,
    project_id: uuid.UUID,
    from_node_id: uuid.UUID,
    to_node_id: uuid.UUID,
    max_depth: int | None = None,
) -> dict:
    settings = get_settings()
    depth = min(
        max_depth or settings.knowledge_graph_max_traversal_depth,
        settings.knowledge_graph_max_traversal_depth,
    )
    gv = get_active_version(db, project_id=project_id)
    sql = text(
        """
        WITH RECURSIVE walk AS (
            SELECT n.id AS node_id, ARRAY[n.id] AS path, 0 AS depth
            FROM knowledge_graph_nodes n
            WHERE n.id = :from_id
              AND n.graph_version_id = :gv_id
              AND n.project_id = :pid
            UNION ALL
            SELECT
                CASE WHEN e.source_node_id = w.node_id
                     THEN e.target_node_id ELSE e.source_node_id END,
                w.path || CASE WHEN e.source_node_id = w.node_id
                     THEN e.target_node_id ELSE e.source_node_id END,
                w.depth + 1
            FROM walk w
            JOIN knowledge_graph_edges e
              ON (e.source_node_id = w.node_id
                  OR e.target_node_id = w.node_id)
             AND e.graph_version_id = :gv_id
            WHERE w.depth < :max_depth
              AND NOT (CASE WHEN e.source_node_id = w.node_id
                     THEN e.target_node_id ELSE e.source_node_id END
                     = ANY(w.path))
        )
        SELECT path, depth FROM walk WHERE node_id = :to_id
        ORDER BY depth ASC LIMIT 1
        """
    )
    row = db.execute(
        sql,
        {
            "from_id": from_node_id,
            "to_id": to_node_id,
            "gv_id": gv.id,
            "pid": project_id,
            "max_depth": depth,
        },
    ).first()
    if row is None:
        return {"found": False, "path": [], "depth": None}
    return {"found": True, "path": list(row[0]), "depth": int(row[1])}


def find_requirement_evidence(
    db: Session, *, project_id: uuid.UUID,
    requirement_node_id: uuid.UUID,
) -> dict:
    gv = get_active_version(db, project_id=project_id)
    node = db.execute(
        select(KnowledgeGraphNode).where(
            KnowledgeGraphNode.id == requirement_node_id,
            KnowledgeGraphNode.graph_version_id == gv.id,
            KnowledgeGraphNode.project_id == project_id,
        )
    ).scalar_one_or_none()
    if node is None:
        raise KnowledgeGraphNotFound("node not found")

    incoming = list(db.execute(
        select(KnowledgeGraphEdge).where(
            KnowledgeGraphEdge.graph_version_id == gv.id,
            KnowledgeGraphEdge.target_node_id == requirement_node_id,
        )
    ).scalars().all())
    src_ids = [e.source_node_id for e in incoming]
    upstream: list = []
    if src_ids:
        upstream = list(db.execute(
            select(KnowledgeGraphNode).where(
                KnowledgeGraphNode.id.in_(src_ids),
                KnowledgeGraphNode.project_id == project_id,
            )
        ).scalars().all())

    return {
        "requirement": {
            "id": node.id, "node_type": node.node_type,
            "entity_id": node.entity_id, "label": node.label,
        },
        "upstream": [
            {"id": n.id, "node_type": n.node_type,
             "entity_id": n.entity_id, "label": n.label}
            for n in upstream
        ],
        "evidence_support_edges": [],
    }


def find_gap_neighborhood(
    db: Session, *, project_id: uuid.UUID, gap_node_id: uuid.UUID,
) -> dict:
    gv = get_active_version(db, project_id=project_id)
    cluster_edges = list(db.execute(
        select(KnowledgeGraphEdge).where(
            KnowledgeGraphEdge.graph_version_id == gv.id,
            KnowledgeGraphEdge.source_node_id == gap_node_id,
            KnowledgeGraphEdge.relation_type
            == "gap_detected_from_cluster",
        )
    ).scalars().all())
    cluster_ids = [e.target_node_id for e in cluster_edges]
    clusters: list = []
    if cluster_ids:
        clusters = list(db.execute(
            select(KnowledgeGraphNode).where(
                KnowledgeGraphNode.id.in_(cluster_ids),
                KnowledgeGraphNode.project_id == project_id,
            )
        ).scalars().all())
    member_edges: list = []
    if clusters:
        member_edges = list(db.execute(
            select(KnowledgeGraphEdge).where(
                KnowledgeGraphEdge.graph_version_id == gv.id,
                KnowledgeGraphEdge.source_node_id.in_(
                    [c.id for c in clusters]
                ),
                KnowledgeGraphEdge.relation_type
                == "cluster_contains_literature_item",
            )
        ).scalars().all())
    item_ids = [e.target_node_id for e in member_edges]
    items: list = []
    if item_ids:
        items = list(db.execute(
            select(KnowledgeGraphNode).where(
                KnowledgeGraphNode.id.in_(item_ids),
                KnowledgeGraphNode.project_id == project_id,
            )
        ).scalars().all())
    return {
        "clusters": [
            {"id": c.id, "entity_id": c.entity_id, "label": c.label}
            for c in clusters
        ],
        "literature_items": [
            {"id": i.id, "entity_id": i.entity_id} for i in items
        ],
    }


def find_source_provenance(
    db: Session, *, project_id: uuid.UUID, source_node_id: uuid.UUID,
) -> dict:
    gv = get_active_version(db, project_id=project_id)
    chunk_edges = list(db.execute(
        select(KnowledgeGraphEdge).where(
            KnowledgeGraphEdge.graph_version_id == gv.id,
            KnowledgeGraphEdge.source_node_id == source_node_id,
            KnowledgeGraphEdge.relation_type == "source_contains_chunk",
        ).limit(1000)
    ).scalars().all())
    chunk_ids = [e.target_node_id for e in chunk_edges]
    chunks: list = []
    if chunk_ids:
        chunks = list(db.execute(
            select(KnowledgeGraphNode).where(
                KnowledgeGraphNode.id.in_(chunk_ids),
                KnowledgeGraphNode.project_id == project_id,
            )
        ).scalars().all())
    incoming = list(db.execute(
        select(KnowledgeGraphEdge).where(
            KnowledgeGraphEdge.graph_version_id == gv.id,
            KnowledgeGraphEdge.target_node_id == source_node_id,
        ).limit(1000)
    ).scalars().all())
    return {
        "source": {"id": source_node_id},
        "chunks": [
            {"id": c.id, "entity_id": c.entity_id} for c in chunks
        ],
        "incoming": [
            {"source_node_id": e.source_node_id,
             "relation_type": e.relation_type,
             "provenance_type": e.provenance_type}
            for e in incoming
        ],
    }
