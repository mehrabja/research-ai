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
    ResearchPlanGenerateResponse,
    ResearchPlanUpdateRequest,
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
            ResearchPlan.status.in_(
                (
                    ResearchPlanStatus.READY.value,
                    ResearchPlanStatus.DRAFT.value,
                )
            ),
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


@router.patch(
    "/{project_id}/research-plan",
    response_model=ResearchPlanRead,
)
def update_plan(
    project_id: uuid.UUID,
    body: ResearchPlanUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ResearchPlanRead:
    get_project(db, user_id=current_user.id, project_id=project_id)
    current = _load_current_plan(db, project_id=project_id)
    latest_version = int(
        db.execute(
            select(func.coalesce(func.max(ResearchPlan.version), 0))
            .where(ResearchPlan.project_id == project_id)
        ).scalar_one()
    )
    plan = ResearchPlan(
        project_id=project_id,
        version=latest_version + 1,
        status=ResearchPlanStatus.DRAFT.value,
        planner_version=current.planner_version,
        planning_mode=current.planning_mode,
        context_hash=current.context_hash,
        literature_run_id=current.literature_run_id,
        domain_id=current.domain_id,
        paper_type_code=current.paper_type_code,
        research_design_code=current.research_design_code,
        research_objective_snapshot=(
            body.research_objective
            if body.research_objective is not None
            else current.research_objective_snapshot
        ),
        research_questions_snapshot=(
            body.research_questions
            if body.research_questions is not None
            else current.research_questions_snapshot
        ),
        hypotheses_snapshot=(
            body.hypotheses
            if body.hypotheses is not None
            else current.hypotheses_snapshot
        ),
        budget=body.budget if body.budget is not None else dict(current.budget or {}),
        plan_meta=body.plan_meta if body.plan_meta is not None else dict(current.plan_meta or {}),
        validation_status="pending",
        validation_errors=None,
        coverage_summary=current.coverage_summary,
        supersedes_plan_id=current.id,
        created_by=current_user.id,
    )
    db.add(plan)
    db.flush()

    old_sections = list(
        db.execute(
            select(ResearchPlanSection)
            .where(ResearchPlanSection.plan_id == current.id)
            .order_by(ResearchPlanSection.display_order.asc())
        ).scalars().all()
    )
    old_reqs = list(
        db.execute(
            select(ResearchEvidenceRequirement)
            .where(ResearchEvidenceRequirement.plan_id == current.id)
        ).scalars().all()
    )
    old_deps = list(
        db.execute(
            select(ResearchPlanDependency)
            .where(ResearchPlanDependency.plan_id == current.id)
        ).scalars().all()
    )

    section_map: dict[uuid.UUID, ResearchPlanSection] = {}
    for old in old_sections:
        clone = ResearchPlanSection(
            plan_id=plan.id,
            section_key=old.section_key,
            title=old.title,
            purpose=old.purpose,
            section_type=old.section_type,
            display_order=old.display_order,
            required=old.required,
            word_budget=old.word_budget,
            budget_weight=old.budget_weight,
            evidence_coverage_target=old.evidence_coverage_target,
            status=old.status,
            section_meta=old.section_meta,
        )
        db.add(clone)
        db.flush()
        section_map[old.id] = clone

    for old in old_reqs:
        db.add(
            ResearchEvidenceRequirement(
                plan_id=plan.id,
                section_id=section_map[old.section_id].id,
                requirement_key=old.requirement_key,
                requirement_type=old.requirement_type,
                description=old.description,
                required=old.required,
                priority=old.priority,
                min_sources=old.min_sources,
                max_sources=old.max_sources,
                preferred_paper_types=old.preferred_paper_types,
                preferred_research_designs=old.preferred_research_designs,
                max_age_years=old.max_age_years,
                full_text_required=old.full_text_required,
                min_relevance_score=old.min_relevance_score,
                coverage_weight=old.coverage_weight,
                requirement_meta=old.requirement_meta,
            )
        )
    for old in old_deps:
        db.add(
            ResearchPlanDependency(
                plan_id=plan.id,
                upstream_section_id=section_map[old.upstream_section_id].id,
                downstream_section_id=section_map[old.downstream_section_id].id,
                dependency_type=old.dependency_type,
                dependency_meta=old.dependency_meta,
            )
        )
    db.commit()
    return _plan_to_read(db, plan)
