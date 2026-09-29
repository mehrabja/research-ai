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


def get_canvas(
    db: Session,
    *,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
) -> ResearchCanvas:
    get_project(db, user_id=user_id, project_id=project_id)
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
