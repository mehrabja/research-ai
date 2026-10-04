"""Dashboard aggregate endpoint."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.dashboard import DashboardStats
from app.services.dashboard import get_dashboard_stats

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardStats)
def dashboard(
    workspace_id: uuid.UUID | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DashboardStats:
    stats = get_dashboard_stats(
        db,
        user_id=current_user.id,
        workspace_id=workspace_id,
    )
    return DashboardStats(
        active_projects=int(stats["active_projects"]),
        saved_sources=int(stats["saved_sources"]),
        evidence_items=int(stats["evidence_items"]),
        active_jobs=int(stats["active_jobs"]),
        storage_bytes=int(stats["storage_bytes"]),
        ai_generation_units=int(stats["ai_generation_units"]),
        ai_generation_limit=(
            int(stats["ai_generation_limit"])
            if stats["ai_generation_limit"] is not None
            else None
        ),
        workspace_count=int(stats["workspace_count"]),
    )
