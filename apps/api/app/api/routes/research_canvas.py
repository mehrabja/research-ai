from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.research_canvas import (
    ResearchCanvasRead,
    ResearchCanvasUpdate,
)
from app.services import research_canvas as canvas_service

router = APIRouter(prefix="/projects", tags=["research-canvas"])


@router.get(
    "/{project_id}/research-canvas",
    response_model=ResearchCanvasRead,
)
def get_research_canvas(
    project_id: uuid.UUID,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ResearchCanvasRead:
    canvas = canvas_service.get_canvas(
        db,
        user_id=current_user.id,
        project_id=project_id,
    )
    result = ResearchCanvasRead.model_validate(canvas)
    response.headers["X-Canvas-Revision"] = str(result.revision)
    return result


@router.put(
    "/{project_id}/research-canvas",
    response_model=ResearchCanvasRead,
)
def save_research_canvas(
    project_id: uuid.UUID,
    payload: ResearchCanvasUpdate,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ResearchCanvasRead:
    canvas = canvas_service.save_canvas(
        db,
        user_id=current_user.id,
        project_id=project_id,
        nodes=[node.model_dump() for node in payload.nodes],
        edges=[edge.model_dump() for edge in payload.edges],
        viewport=payload.viewport.model_dump(),
        expected_revision=payload.expected_revision,
    )
    result = ResearchCanvasRead.model_validate(canvas)
    response.headers["X-Canvas-Revision"] = str(result.revision)
    return result
