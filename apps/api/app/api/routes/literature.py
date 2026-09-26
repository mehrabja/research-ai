"""M23 — Literature intelligence routes.

* POST /analyze returns a unified response:
    - async mode: 202 + LiteratureAnalyzeResponse(status="queued", job_id=...)
    - sync mode:  200 + LiteratureAnalyzeResponse(status=..., run=...)
  No synthetic LiteratureIntelligenceRun is returned.
* PATCH screening override commits user intent FIRST, then
  best-effort enqueues recompute. If enqueue fails, an explicit
  literature_analysis_failed event records the reason.
* All list endpoints paginated (limit <= 200).
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.config import get_settings
from app.db.models.literature import (
    LiteratureCluster,
    LiteratureGap,
    LiteratureIntelligenceRun,
    ProjectLiteratureItem,
)
from app.db.models.project import ProjectEvent
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.literature import (
    LiteratureAnalyzeRequest,
    LiteratureAnalyzeResponse,
    LiteratureClusterListResponse,
    LiteratureClusterRead,
    LiteratureGapListResponse,
    LiteratureGapRead,
    LiteratureItemRead,
    LiteratureListResponse,
    LiteratureRunListResponse,
    LiteratureRunRead,
    LiteratureScreeningUpdate,
)
from app.services.literature import corpus, pipeline
from app.services.literature import jobs as lit_jobs
from app.services.projects import get_project

router = APIRouter(prefix="/projects", tags=["literature"])


@router.get(
    "/{project_id}/literature",
    response_model=LiteratureListResponse,
)
def list_literature(
    project_id: uuid.UUID,
    screening_status: str | None = Query(default=None),
    relevance_min: float | None = Query(default=None, ge=0.0, le=1.0),
    paper_type: str | None = Query(default=None),
    research_design: str | None = Query(default=None),
    analysis_status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LiteratureListResponse:
    get_project(db, user_id=current_user.id, project_id=project_id)

    base = select(ProjectLiteratureItem).where(
        ProjectLiteratureItem.project_id == project_id
    )
    if screening_status:
        base = base.where(
            ProjectLiteratureItem.screening_status == screening_status
        )
    if relevance_min is not None:
        base = base.where(
            ProjectLiteratureItem.relevance_score.is_not(None),
            ProjectLiteratureItem.relevance_score >= relevance_min,
        )
    if paper_type:
        base = base.where(
            ProjectLiteratureItem.paper_type_code == paper_type
        )
    if research_design:
        base = base.where(
            ProjectLiteratureItem.research_design_code == research_design
        )
    if analysis_status:
        base = base.where(
            ProjectLiteratureItem.analysis_status == analysis_status
        )

    total = int(
        db.execute(
            select(func.count()).select_from(base.subquery())
        ).scalar_one()
    )
    rows = list(
        db.execute(
            base.order_by(
                ProjectLiteratureItem.created_at.asc(),
                ProjectLiteratureItem.id.asc(),
            )
            .limit(limit)
            .offset(offset)
        ).scalars().all()
    )
    return LiteratureListResponse(
        items=[LiteratureItemRead.model_validate(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/{project_id}/literature/analyze",
    response_model=LiteratureAnalyzeResponse,
    status_code=202,
)
def analyze_literature(
    project_id: uuid.UUID,
    body: LiteratureAnalyzeRequest,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LiteratureAnalyzeResponse:
    get_project(db, user_id=current_user.id, project_id=project_id)
    settings = get_settings()

    if settings.literature_async_jobs:
        job_id = lit_jobs.enqueue_literature_analysis(
            db,
            project_id=project_id,
            user_id=current_user.id,
            force=body.force,
        )
        if job_id is None:
            raise HTTPException(
                status_code=500,
                detail="failed to enqueue literature analysis",
            )
        db.commit()
        response.status_code = 202
        return LiteratureAnalyzeResponse(
            status="queued", job_id=job_id, run=None
        )

    result = pipeline.run_literature_analysis(
        db,
        user_id=current_user.id,
        project_id=project_id,
        force=body.force,
        commit=True,
    )
    response.status_code = 200
    return LiteratureAnalyzeResponse(
        status=result.run.status,
        job_id=None,
        run=LiteratureRunRead.model_validate(result.run),
    )


@router.patch(
    "/{project_id}/literature/{item_id}",
    response_model=LiteratureItemRead,
)
def update_screening(
    project_id: uuid.UUID,
    item_id: uuid.UUID,
    body: LiteratureScreeningUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LiteratureItemRead:
    item = corpus.get_literature_item_for_project(
        db,
        user_id=current_user.id,
        project_id=project_id,
        item_id=item_id,
    )
    previous = item.screening_status
    item.screening_status = body.screening_status
    item.manual_override = True
    item.manual_override_at = datetime.now(UTC)
    item.manual_override_by = current_user.id
    item.manual_override_reason = body.reason

    db.add(
        ProjectEvent(
            project_id=project_id,
            user_id=current_user.id,
            event_type="literature_screening_overridden",
            event_meta={
                "item_id": str(item.id),
                "previous_status": previous,
                "new_status": body.screening_status,
                "reason": body.reason,
            },
        )
    )
    # 1. Commit user intent — durable even if enqueue fails.
    db.commit()
    db.refresh(item)

    # 2. Best-effort recompute trigger. Helper does NOT commit.
    job_id = lit_jobs.enqueue_literature_analysis(
        db,
        project_id=project_id,
        user_id=current_user.id,
        force=False,
    )
    if job_id is None:
        db.add(
            ProjectEvent(
                project_id=project_id,
                user_id=current_user.id,
                event_type="literature_analysis_failed",
                event_meta={
                    "phase": "enqueue_after_override",
                    "item_id": str(item.id),
                },
            )
        )
        db.commit()
    else:
        db.commit()

    return LiteratureItemRead.model_validate(item)


@router.get(
    "/{project_id}/literature/clusters",
    response_model=LiteratureClusterListResponse,
)
def list_clusters(
    project_id: uuid.UUID,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LiteratureClusterListResponse:
    get_project(db, user_id=current_user.id, project_id=project_id)
    base = select(LiteratureCluster).where(
        LiteratureCluster.project_id == project_id
    )
    total = int(
        db.execute(
            select(func.count()).select_from(base.subquery())
        ).scalar_one()
    )
    rows = list(
        db.execute(
            base.order_by(
                LiteratureCluster.created_at.asc(),
                LiteratureCluster.id.asc(),
            )
            .limit(limit)
            .offset(offset)
        ).scalars().all()
    )
    return LiteratureClusterListResponse(
        items=[LiteratureClusterRead.model_validate(r) for r in rows],
        total=total,
    )


@router.get(
    "/{project_id}/literature/gaps",
    response_model=LiteratureGapListResponse,
)
def list_gaps(
    project_id: uuid.UUID,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LiteratureGapListResponse:
    get_project(db, user_id=current_user.id, project_id=project_id)
    base = select(LiteratureGap).where(
        LiteratureGap.project_id == project_id
    )
    total = int(
        db.execute(
            select(func.count()).select_from(base.subquery())
        ).scalar_one()
    )
    rows = list(
        db.execute(
            base.order_by(
                LiteratureGap.created_at.asc(),
                LiteratureGap.id.asc(),
            )
            .limit(limit)
            .offset(offset)
        ).scalars().all()
    )
    return LiteratureGapListResponse(
        items=[LiteratureGapRead.model_validate(r) for r in rows],
        total=total,
    )


@router.get(
    "/{project_id}/literature/runs",
    response_model=LiteratureRunListResponse,
)
def list_runs(
    project_id: uuid.UUID,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LiteratureRunListResponse:
    get_project(db, user_id=current_user.id, project_id=project_id)
    base = select(LiteratureIntelligenceRun).where(
        LiteratureIntelligenceRun.project_id == project_id
    )
    total = int(
        db.execute(
            select(func.count()).select_from(base.subquery())
        ).scalar_one()
    )
    rows = list(
        db.execute(
            base.order_by(
                LiteratureIntelligenceRun.created_at.desc(),
                LiteratureIntelligenceRun.id.desc(),
            )
            .limit(limit)
            .offset(offset)
        ).scalars().all()
    )
    return LiteratureRunListResponse(
        items=[LiteratureRunRead.model_validate(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )
