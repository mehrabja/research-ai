"""M24 — Research plan routes."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.config import get_settings
from app.core.exceptions import ResearchPlanNotFound
from app.db.models.research_plan import (
    ResearchEvidenceRequirement,
    ResearchPlan,
    ResearchPlanDependency,
    ResearchPlanSection,
)
from app.db.models.user import User
from app.db.session import get_db
from app.domain.research_plan import ResearchPlanStatus
from app.schemas.research_plan import (
    ResearchEvidenceRequirementRead,
    ResearchPlanCoverageRead,
    ResearchPlanDependencyRead,
    ResearchPlanGenerateRequest,
    ResearchPlanPatchRequest,
    ResearchPlanRestoreRequest,
    ResearchPlanGenerateResponse,
    ResearchPlanRead,
    ResearchPlanSectionRead,
    ResearchPlanValidationRead,
    ResearchPlanVersionListResponse,
)
from app.services.projects import get_project
from app.services.research_planning import (
    jobs as jobs_svc,
)
from app.services.research_planning import (
    planner as planner_svc,
)
from app.services.research_planning import (
    validation as validation_svc,
)
from app.services.research_planning import revisions as revisions_svc

router = APIRouter(prefix="/projects", tags=["research-plan"])


class _ReqView:
    __slots__ = ("requirement_key", "section_key")

    def __init__(self, key, section_key):
        self.requirement_key = key
        self.section_key = section_key


def _plan_to_read(db: Session, plan: ResearchPlan) -> ResearchPlanRead:
    sections = list(
        db.execute(
            select(ResearchPlanSection)
            .where(ResearchPlanSection.plan_id == plan.id)
            .order_by(ResearchPlanSection.display_order.asc())
        ).scalars().all()
    )
    reqs = list(
        db.execute(
            select(ResearchEvidenceRequirement)
            .where(ResearchEvidenceRequirement.plan_id == plan.id)
        ).scalars().all()
    )
    deps = list(
        db.execute(
            select(ResearchPlanDependency)
            .where(ResearchPlanDependency.plan_id == plan.id)
        ).scalars().all()
    )
    base = ResearchPlanRead.model_validate(plan)
    return base.model_copy(update={
        "sections": [
            ResearchPlanSectionRead.model_validate(s) for s in sections
        ],
        "evidence_requirements": [
            ResearchEvidenceRequirementRead.model_validate(r)
            for r in reqs
        ],
        "dependencies": [
            ResearchPlanDependencyRead.model_validate(d) for d in deps
        ],
    })


def _load_current_plan(
    db: Session, *, project_id: uuid.UUID
) -> ResearchPlan:
    plan = db.execute(
        select(ResearchPlan)
        .where(
            ResearchPlan.project_id == project_id,
            ResearchPlan.status == ResearchPlanStatus.READY.value,
        )
        .order_by(ResearchPlan.version.desc())
        .limit(1)
    ).scalar_one_or_none()
    if plan is None:
        raise ResearchPlanNotFound()
    return plan


@router.post(
    "/{project_id}/research-plan/generate",
    response_model=ResearchPlanGenerateResponse,
)
def generate(
    project_id: uuid.UUID,
    body: ResearchPlanGenerateRequest,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ResearchPlanGenerateResponse:
    get_project(db, user_id=current_user.id, project_id=project_id)
    settings = get_settings()

    effective_async = bool(body.async_) and bool(
        settings.research_plan_async_jobs or body.async_
    )

    if effective_async:
        job_id = jobs_svc.enqueue_research_plan(
            db,
            project_id=project_id,
            user_id=current_user.id,
            force=body.force,
        )
        if job_id is None:
            response.status_code = 500
            return ResearchPlanGenerateResponse(
                status="failed", job_id=None, plan=None
            )
        db.commit()
        response.status_code = 202
        return ResearchPlanGenerateResponse(
            status="queued", job_id=job_id, plan=None
        )

    result = planner_svc.generate_research_plan(
        db,
        user_id=current_user.id,
        project_id=project_id,
        force=body.force,
        commit=True,
    )
    response.status_code = 200
    if result.plan is None:
        return ResearchPlanGenerateResponse(
            status=result.run.status, job_id=None, plan=None
        )
    return ResearchPlanGenerateResponse(
        status=result.run.status,
        job_id=None,
        plan=_plan_to_read(db, result.plan),
    )


@router.get(
    "/{project_id}/research-plan",
    response_model=ResearchPlanRead,
)
def get_current(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ResearchPlanRead:
    get_project(db, user_id=current_user.id, project_id=project_id)
    plan = _load_current_plan(db, project_id=project_id)
    return _plan_to_read(db, plan)


@router.get(
    "/{project_id}/research-plan/versions",
    response_model=ResearchPlanVersionListResponse,
)
def list_versions(
    project_id: uuid.UUID,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ResearchPlanVersionListResponse:
    get_project(db, user_id=current_user.id, project_id=project_id)
    base = select(ResearchPlan).where(
        ResearchPlan.project_id == project_id
    )
    total = int(
        db.execute(
            select(func.count()).select_from(base.subquery())
        ).scalar_one()
    )
    rows = list(
        db.execute(
            base.order_by(ResearchPlan.version.desc())
            .limit(limit).offset(offset)
        ).scalars().all()
    )
    return ResearchPlanVersionListResponse(
        items=[_plan_to_read(db, r) for r in rows],
        total=total, limit=limit, offset=offset,
    )


@router.patch(
    "/{project_id}/research-plan",
    response_model=ResearchPlanRead,
)
def save_plan_revision(
    project_id: uuid.UUID,
    body: ResearchPlanPatchRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ResearchPlanRead:
    plan = revisions_svc.save_revision(
        db,
        project_id=project_id,
        user_id=current_user.id,
        body=body.model_dump(exclude_unset=True),
    )
    db.commit()
    return _plan_to_read(db, plan)


@router.post(
    "/{project_id}/research-plan/restore",
    response_model=ResearchPlanRead,
)
def restore_plan_version(
    project_id: uuid.UUID,
    body: ResearchPlanRestoreRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ResearchPlanRead:
    plan = revisions_svc.restore_version(
        db,
        project_id=project_id,
        user_id=current_user.id,
        target_version=body.target_version,
    )
    db.commit()
    return _plan_to_read(db, plan)


@router.get(
    "/{project_id}/research-plan/coverage",
    response_model=ResearchPlanCoverageRead,
)
def get_coverage(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ResearchPlanCoverageRead:
    get_project(db, user_id=current_user.id, project_id=project_id)
    plan = _load_current_plan(db, project_id=project_id)
    summary = plan.coverage_summary or {}
    return ResearchPlanCoverageRead(
        coverage_score=float(plan.coverage_score or 0.0),
        coverage_state=str(summary.get("coverage_state", "unknown")),
        per_requirement=list(summary.get("per_requirement") or []),
    )


@router.post(
    "/{project_id}/research-plan/validate",
    response_model=ResearchPlanValidationRead,
)
def validate_plan(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ResearchPlanValidationRead:
    get_project(db, user_id=current_user.id, project_id=project_id)
    plan = _load_current_plan(db, project_id=project_id)

    sections = list(
        db.execute(
            select(ResearchPlanSection)
            .where(ResearchPlanSection.plan_id == plan.id)
            .order_by(ResearchPlanSection.display_order.asc())
        ).scalars().all()
    )
    reqs = list(
        db.execute(
            select(ResearchEvidenceRequirement)
            .where(ResearchEvidenceRequirement.plan_id == plan.id)
        ).scalars().all()
    )
    deps = list(
        db.execute(
            select(ResearchPlanDependency)
            .where(ResearchPlanDependency.plan_id == plan.id)
        ).scalars().all()
    )
    section_key_by_id = {s.id: s.section_key for s in sections}
    edges: list[tuple[str, str]] = []
    for d in deps:
        up = section_key_by_id.get(d.upstream_section_id)
        down = section_key_by_id.get(d.downstream_section_id)
        if up and down:
            edges.append((up, down))

    vres = validation_svc.validate_plan_structure(
        sections=sections,
        requirements=[
            _ReqView(
                r.requirement_key,
                section_key_by_id.get(r.section_id, ""),
            )
            for r in reqs
        ],
        budget=plan.budget or {},
        dependency_edges=edges,
        plan_section_key_of=lambda s: s.section_key,
        category_resolved=True,
    )
    return ResearchPlanValidationRead(
        validation_status="valid" if vres.valid() else "invalid",
        validation_errors=list(vres.errors),
        completeness_score=vres.score,
    )
