"""M35 — Orchestration API routes."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.config import get_settings
from app.core.exceptions import (
    OrchestrationInvalid,
    OrchestrationNotFound,
)
from app.db.models.orchestration import (
    ResearchOrchestrationNode,
    ResearchOrchestrationRun,
)
from app.db.models.user import User
from app.db.session import get_db
from app.domain.orchestration import (
    NodeStatus,
    RunStatus,
    is_terminal_run,
    validate_run_transition,
)
from app.schemas.orchestration import (
    OrchestrationCancelResponse,
    OrchestrationNodeListResponse,
    OrchestrationNodeRead,
    OrchestrationPauseResponse,
    OrchestrationRunDetailRead,
    OrchestrationRunListResponse,
    OrchestrationRunRead,
    OrchestrationRunRequest,
    OrchestrationRunResponse,
    OrchestrationToolListResponse,
    OrchestrationToolRead,
    OrchestrationValidationRead,
)
from app.services.orchestration import jobs as orch_jobs
from app.services.orchestration import persistence as orch_persist
from app.services.orchestration.registry import (
    get_tool,
    list_tools,
)
from app.services.reports import get_report

router = APIRouter(prefix="/reports", tags=["orchestration"])


def _load_run(
    db: Session, *, report_id: uuid.UUID, run_id: uuid.UUID,
) -> ResearchOrchestrationRun:
    run = db.execute(
        select(ResearchOrchestrationRun).where(
            ResearchOrchestrationRun.id == run_id,
            ResearchOrchestrationRun.report_id == report_id,
        )
    ).scalar_one_or_none()
    if run is None:
        raise OrchestrationNotFound()
    return run


@router.post(
    "/{report_id}/orchestration/run",
    response_model=OrchestrationRunResponse,
)
def run_orchestration(
    report_id: uuid.UUID,
    body: OrchestrationRunRequest,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OrchestrationRunResponse:
    report = get_report(
        db, user_id=current_user.id, report_id=report_id,
    )
    if report.project_id is None:
        raise OrchestrationInvalid("report has no project")
    settings = get_settings()

    effective_async = bool(body.async_)
    if effective_async and not settings.orchestration_async_jobs:
        effective_async = False

    if effective_async:
        job_id = orch_jobs.enqueue_orchestration(
            db,
            project_id=report.project_id,
            report_id=report_id,
            user_id=current_user.id,
            goal=body.goal,
            strategy=body.strategy,
            payload=body.payload,
            force=body.force,
        )
        response.status_code = 202
        return OrchestrationRunResponse(
            status="queued", job_id=job_id,
        )

    persisted = orch_persist.run_m35_persisted(
        db,
        project_id=report.project_id,
        report_id=report_id,
        user_id=current_user.id,
        goal=body.goal,
        strategy=body.strategy,
        payload=body.payload,
        force=body.force,
        commit=True,
    )
    response.status_code = 200
    return OrchestrationRunResponse(
        status=persisted.run.status,
        run_id=persisted.run.id,
        context_hash=persisted.run.context_hash,
        node_count=int(persisted.run.node_count or 0),
        completed_node_count=int(
            persisted.run.completed_node_count or 0
        ),
        failed_node_count=int(
            persisted.run.failed_node_count or 0
        ),
    )


@router.get(
    "/{report_id}/orchestration/current",
    response_model=OrchestrationRunDetailRead,
)
def get_current_orchestration(
    report_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OrchestrationRunDetailRead:
    get_report(db, user_id=current_user.id, report_id=report_id)
    run = db.execute(
        select(ResearchOrchestrationRun)
        .where(ResearchOrchestrationRun.report_id == report_id)
        .order_by(
            ResearchOrchestrationRun.created_at.desc(),
            ResearchOrchestrationRun.id.desc(),
        )
        .limit(1)
    ).scalar_one_or_none()
    if run is None:
        raise OrchestrationNotFound()

    nodes = list(db.execute(
        select(ResearchOrchestrationNode)
        .where(ResearchOrchestrationNode.run_id == run.id)
        .order_by(ResearchOrchestrationNode.sequence.asc())
    ).scalars().all())
    return OrchestrationRunDetailRead(
        run=OrchestrationRunRead.model_validate(run),
        nodes=[
            OrchestrationNodeRead.model_validate(n) for n in nodes
        ],
    )


@router.get(
    "/{report_id}/orchestration/runs",
    response_model=OrchestrationRunListResponse,
)
def list_orchestration_runs(
    report_id: uuid.UUID,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OrchestrationRunListResponse:
    get_report(db, user_id=current_user.id, report_id=report_id)
    base = select(ResearchOrchestrationRun).where(
        ResearchOrchestrationRun.report_id == report_id
    )
    total = int(db.execute(
        select(func.count()).select_from(base.subquery())
    ).scalar_one())
    rows = list(db.execute(
        base.order_by(
            ResearchOrchestrationRun.created_at.desc(),
            ResearchOrchestrationRun.id.desc(),
        ).limit(limit).offset(offset)
    ).scalars().all())
    return OrchestrationRunListResponse(
        items=[OrchestrationRunRead.model_validate(r) for r in rows],
        total=total, limit=limit, offset=offset,
    )


@router.get(
    "/{report_id}/orchestration/runs/{run_id}",
    response_model=OrchestrationRunDetailRead,
)
def get_orchestration_run(
    report_id: uuid.UUID,
    run_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OrchestrationRunDetailRead:
    get_report(db, user_id=current_user.id, report_id=report_id)
    run = _load_run(db, report_id=report_id, run_id=run_id)
    nodes = list(db.execute(
        select(ResearchOrchestrationNode)
        .where(ResearchOrchestrationNode.run_id == run.id)
        .order_by(ResearchOrchestrationNode.sequence.asc())
    ).scalars().all())
    return OrchestrationRunDetailRead(
        run=OrchestrationRunRead.model_validate(run),
        nodes=[
            OrchestrationNodeRead.model_validate(n) for n in nodes
        ],
    )


@router.get(
    "/{report_id}/orchestration/runs/{run_id}/nodes",
    response_model=OrchestrationNodeListResponse,
)
def list_orchestration_nodes(
    report_id: uuid.UUID,
    run_id: uuid.UUID,
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OrchestrationNodeListResponse:
    get_report(db, user_id=current_user.id, report_id=report_id)
    run = _load_run(db, report_id=report_id, run_id=run_id)
    base = select(ResearchOrchestrationNode).where(
        ResearchOrchestrationNode.run_id == run.id
    )
    total = int(db.execute(
        select(func.count()).select_from(base.subquery())
    ).scalar_one())
    rows = list(db.execute(
        base.order_by(ResearchOrchestrationNode.sequence.asc())
        .limit(limit).offset(offset)
    ).scalars().all())
    return OrchestrationNodeListResponse(
        items=[
            OrchestrationNodeRead.model_validate(n) for n in rows
        ],
        total=total, limit=limit, offset=offset,
    )


@router.post(
    "/{report_id}/orchestration/runs/{run_id}/pause",
    response_model=OrchestrationPauseResponse,
)
def pause_orchestration(
    report_id: uuid.UUID,
    run_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OrchestrationPauseResponse:
    get_report(db, user_id=current_user.id, report_id=report_id)
    run = _load_run(db, report_id=report_id, run_id=run_id)
    if is_terminal_run(run.status):
        raise OrchestrationInvalid("run is already terminal")
    validate_run_transition(
        run.status, RunStatus.PAUSED.value,
    )
    run.status = RunStatus.PAUSED.value
    db.commit()
    return OrchestrationPauseResponse(
        status=run.status, run_id=run.id,
    )


@router.post(
    "/{report_id}/orchestration/runs/{run_id}/cancel",
    response_model=OrchestrationCancelResponse,
)
def cancel_orchestration(
    report_id: uuid.UUID,
    run_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OrchestrationCancelResponse:
    get_report(db, user_id=current_user.id, report_id=report_id)
    run = _load_run(db, report_id=report_id, run_id=run_id)
    if is_terminal_run(run.status):
        raise OrchestrationInvalid("run is already terminal")
    validate_run_transition(
        run.status, RunStatus.CANCELLED.value,
    )
    run.status = RunStatus.CANCELLED.value
    run.cancelled_at = datetime.now(UTC)
    db.commit()
    return OrchestrationCancelResponse(
        status=run.status, run_id=run.id,
    )


@router.get(
    "/{report_id}/orchestration/tools",
    response_model=OrchestrationToolListResponse,
)
def list_orchestration_tools(
    report_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OrchestrationToolListResponse:
    get_report(db, user_id=current_user.id, report_id=report_id)
    keys = list_tools()
    items: list[OrchestrationToolRead] = []
    for key in keys:
        try:
            spec, _fn = get_tool(key)
        except Exception:
            continue
        items.append(OrchestrationToolRead(
            key=spec.key,
            version=spec.version,
            description=spec.description,
            permission=spec.permission,
            deterministic=spec.deterministic,
        ))
    return OrchestrationToolListResponse(items=items)


@router.post(
    "/{report_id}/orchestration/runs/{run_id}/validate",
    response_model=OrchestrationValidationRead,
)
def validate_orchestration(
    report_id: uuid.UUID,
    run_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OrchestrationValidationRead:
    get_report(db, user_id=current_user.id, report_id=report_id)
    run = _load_run(db, report_id=report_id, run_id=run_id)
    errors: list[str] = []
    warnings: list[str] = []

    if not run.context_hash:
        errors.append("missing_context_hash")

    nodes = list(db.execute(
        select(ResearchOrchestrationNode).where(
            ResearchOrchestrationNode.run_id == run.id
        )
    ).scalars().all())
    if not nodes:
        errors.append("no_nodes_materialized")
    for n in nodes:
        if n.status == NodeStatus.FAILED.value:
            warnings.append(f"node_failed:{n.node_key}")

    return OrchestrationValidationRead(
        validation_status="valid" if not errors else "invalid",
        validation_errors=errors,
        warnings=warnings,
    )
