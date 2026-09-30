from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.db.models.research_canvas import ResearchCanvas
from app.services.projects import get_project


class CanvasRevisionConflict(AppError):
    code = "CANVAS_REVISION_CONFLICT"
    status_code = 409
    message = "Research canvas changed since it was loaded."


class CanvasInvalid(AppError):
    code = "CANVAS_INVALID"
    status_code = 422
    message = "Research canvas payload is invalid."


def _validate_canvas_graph(
    *,
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
) -> None:
    node_ids = [str(node.get("id", "")) for node in nodes]
    if any(not node_id for node_id in node_ids):
        raise CanvasInvalid("canvas node id is required")
    if len(node_ids) != len(set(node_ids)):
        raise CanvasInvalid("canvas node ids must be unique")

    node_set = set(node_ids)
    for node in nodes:
        ref_type = node.get("ref_type")
        ref_id = node.get("ref_id")
        evidence_key = node.get("evidence_key")
        if ref_type is not None and ref_id is None:
            raise CanvasInvalid("ref_id is required when ref_type is set")
        if ref_type == "evidence" and not evidence_key:
            raise CanvasInvalid(
                "evidence_key is required for evidence canvas nodes"
            )

    edge_ids = [str(edge.get("id", "")) for edge in edges]
    if any(not edge_id for edge_id in edge_ids):
        raise CanvasInvalid("canvas edge id is required")
    if len(edge_ids) != len(set(edge_ids)):
        raise CanvasInvalid("canvas edge ids must be unique")
    for edge in edges:
        source = str(edge.get("source", ""))
        target = str(edge.get("target", ""))
        if source not in node_set or target not in node_set:
            raise CanvasInvalid("canvas edge references an unknown node")
        if source == target:
            raise CanvasInvalid("canvas self-edges are not allowed")


def get_canvas(
    db: Session,
    *,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
) -> ResearchCanvas:
    get_project(db, user_id=user_id, project_id=project_id)
    _validate_canvas_graph(nodes=nodes, edges=edges)
    canvas = db.execute(
        select(ResearchCanvas).where(
            ResearchCanvas.project_id == project_id
        )
    ).scalar_one_or_none()
    if canvas is None:
        canvas = ResearchCanvas(
            project_id=project_id,
            revision=1,
            nodes=[],
            edges=[],
            viewport={"x": 0, "y": 0, "zoom": 1},
            updated_by_user=user_id,
        )
        db.add(canvas)
        db.commit()
        db.refresh(canvas)
    return canvas


def save_canvas(
    db: Session,
    *,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    viewport: dict[str, Any],
    expected_revision: int | None,
) -> ResearchCanvas:
    get_project(db, user_id=user_id, project_id=project_id)
    canvas = db.execute(
        select(ResearchCanvas)
        .where(ResearchCanvas.project_id == project_id)
        .with_for_update()
    ).scalar_one_or_none()

    if canvas is None:
        if expected_revision not in (None, 1):
            raise CanvasRevisionConflict()
        canvas = ResearchCanvas(
            project_id=project_id,
            revision=1,
            nodes=nodes,
            edges=edges,
            viewport=viewport,
            updated_by_user=user_id,
        )
        db.add(canvas)
    else:
        if (
            expected_revision is not None
            and expected_revision != canvas.revision
        ):
            raise CanvasRevisionConflict()
        canvas.revision += 1
        canvas.nodes = nodes
        canvas.edges = edges
        canvas.viewport = viewport
        canvas.updated_by_user = user_id

    db.commit()
    db.refresh(canvas)
    return canvas
