"""Knowledge graph export for authorized project consumers."""
from __future__ import annotations

import csv
import io
import uuid
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.knowledge_graph import (
    KnowledgeGraphEdge,
    KnowledgeGraphNode,
)
from app.services.knowledge_graph.queries import get_active_version

ExportFormat = Literal["json", "csv"]


def export_graph(
    db: Session,
    *,
    project_id: uuid.UUID,
    export_format: ExportFormat,
) -> tuple[str, str]:
    gv = get_active_version(db, project_id=project_id)

    nodes = list(
        db.execute(
            select(KnowledgeGraphNode)
            .where(KnowledgeGraphNode.graph_version_id == gv.id)
            .order_by(KnowledgeGraphNode.node_key.asc())
        ).scalars().all()
    )
    edges = list(
        db.execute(
            select(KnowledgeGraphEdge)
            .where(KnowledgeGraphEdge.graph_version_id == gv.id)
            .order_by(KnowledgeGraphEdge.edge_key.asc())
        ).scalars().all()
    )

    if export_format == "json":
        import json

        payload = {
            "graph_version_id": str(gv.id),
            "version": gv.version,
            "graph_version": gv.graph_version,
            "context_hash": gv.context_hash,
            "nodes": [
                {
                    "id": str(n.id),
                    "node_type": n.node_type,
                    "node_key": n.node_key,
                    "entity_id": str(n.entity_id),
                    "label": n.label,
                    "metadata": n.node_meta,
                }
                for n in nodes
            ],
            "edges": [
                {
                    "id": str(e.id),
                    "source_node_id": str(e.source_node_id),
                    "target_node_id": str(e.target_node_id),
                    "relation_type": e.relation_type,
                    "provenance_type": e.provenance_type,
                    "provenance_ref": e.provenance_ref,
                    "confidence": (
                        float(e.confidence) if e.confidence is not None else None
                    ),
                    "weight": float(e.weight),
                    "metadata": e.edge_meta,
                }
                for e in edges
            ],
        }
        return json.dumps(payload, ensure_ascii=False), "application/json"

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "record_type",
        "id",
        "source_node_id",
        "target_node_id",
        "node_type",
        "node_key",
        "entity_id",
        "label",
        "relation_type",
        "provenance_type",
        "provenance_ref",
        "confidence",
        "weight",
    ])
    for n in nodes:
        writer.writerow([
            "node",
            str(n.id),
            "",
            "",
            n.node_type,
            n.node_key,
            str(n.entity_id),
            n.label or "",
            "",
            "",
            "",
            "",
            "",
        ])
    for e in edges:
        writer.writerow([
            "edge",
            str(e.id),
            str(e.source_node_id),
            str(e.target_node_id),
            "",
            "",
            "",
            "",
            e.relation_type,
            e.provenance_type,
            e.provenance_ref or "",
            float(e.confidence) if e.confidence is not None else "",
            float(e.weight),
        ])
    return buf.getvalue(), "text/csv"
