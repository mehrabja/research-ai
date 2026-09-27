"""Global search routes."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.search import GlobalSearchItem, GlobalSearchResponse
from app.services.global_search import global_search

router = APIRouter(prefix="/search", tags=["search"])


@router.get("", response_model=GlobalSearchResponse)
def search(
    q: str = Query(..., min_length=1, max_length=500),
    workspace_id: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GlobalSearchResponse:
    rows, total = global_search(
        db,
        user_id=current_user.id,
        query=q,
        workspace_id=workspace_id,
        limit=limit,
        offset=offset,
    )
    return GlobalSearchResponse(
        query=q,
        items=[
            GlobalSearchItem(
                type=row.type,
                id=row.id,
                title=row.title,
                snippet=row.snippet,
                workspace_id=row.workspace_id,
                project_id=row.project_id,
                report_id=row.report_id,
            )
            for row in rows
        ],
        total=total,
        limit=limit,
        offset=offset,
    )
