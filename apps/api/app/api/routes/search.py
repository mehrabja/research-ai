from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.search import SearchResponse, SearchResult
from app.services.search import search_workspace

router = APIRouter(prefix="/search", tags=["search"])


@router.get("", response_model=SearchResponse)
def search(
    q: str = Query(..., min_length=2, max_length=200),
    workspace_id: uuid.UUID = Query(...),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SearchResponse:
    rows, total = search_workspace(
        db,
        workspace_id=workspace_id,
        user_id=current_user.id,
        query=q,
        limit=limit,
    )
    return SearchResponse(
        query=q.strip(),
        workspace_id=workspace_id,
        items=[SearchResult.model_validate(row) for row in rows],
        total=total,
    )
