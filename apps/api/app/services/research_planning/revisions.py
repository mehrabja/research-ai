from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import ResearchPlanNotFound
from app.db.models.research_plan import (
    ResearchEvidenceRequirement,
    ResearchPlan,
    ResearchPlanDependency,
    ResearchPlanSection,
)
from app.services.projects import get_project


def _copy_plan(
    db: Session,
    *,
    source: ResearchPlan,
    created_by: uuid.UUID,
    status: str,
    overrides: dict | None = None,
) -> ResearchPlan:
    latest = db.execute(
        select(ResearchPlan)
        .where(ResearchPlan.project_id == source.project_id)
        .order_by(ResearchPlan.version.desc())
        .limit(1)
        .with_for_update()
    ).scalar_one_or_none()
    next_version = (latest.version if latest is not None else 0) + 1

    overrides = overrides or {}
    plan = ResearchPlan(
        project_id=source.project_id,
        version=next_version,
        status=status,
        planner_version=source.planner_version,
        planning_mode=overrides.get("planning_mode", source.planning_mode),
        context_hash=f"manual:{source.id}:{next_version}",
        literature_run_id=source.literature_run_id,
        domain_id=source.domain_id,
        paper_type_code=source.paper_type_code,
        research_design_code=source.research_design_code,
        research_objective_snapshot=overrides.get(
            "research_objective_snapshot", source.research_objective_snapshot
        ),
        research_questions_snapshot=overrides.get(
            "research_questions_snapshot", source.research_questions_snapshot
        ),
        hypotheses_snapshot=overrides.get(
            "hypotheses_snapshot", source.hypotheses_snapshot
        ),
        budget=overrides.get("budget", source.budget),
        completeness_score=source.completeness_score,
        coverage_score=source.coverage_score,
        validation_status=source.validation_status,
        validation_errors=source.validation_errors,
        coverage_summary=source.coverage_summary,
        supersedes_plan_id=source.id,
        created_by=created_by,
    )
    db.add(plan)
    db.flush()

    section_map: dict[uuid.UUID, uuid.UUID] = {}
    source_sections = list(
        db.execute(
            select(ResearchPlanSection)
            .where(ResearchPlanSection.plan_id == source.id)
            .order_by(ResearchPlanSection.display_order.asc())
        ).scalars()
    )
    for section in source_sections:
        copied = ResearchPlanSection(
            plan_id=plan.id,
            section_key=section.section_key,
            title=section.title,
            purpose=section.purpose,
            section_type=section.section_type,
            display_order=section.display_order,
            required=section.required,
            word_budget=section.word_budget,
            budget_weight=section.budget_weight,
            evidence_coverage_target=section.evidence_coverage_target,
            status=section.status,
            section_meta=section.section_meta,
        )
        db.add(copied)
        db.flush()
        section_map[section.id] = copied.id

    requirements = list(
        db.execute(
            select(ResearchEvidenceRequirement)
            .where(ResearchEvidenceRequirement.plan_id == source.id)
        ).scalars()
    )
    for req in requirements:
        mapped_section_id = section_map.get(req.section_id)
        if mapped_section_id is None:
            continue
        db.add(
            ResearchEvidenceRequirement(
                plan_id=plan.id,
                section_id=mapped_section_id,
                requirement_key=req.requirement_key,
                requirement_type=req.requirement_type,
                description=req.description,
                required=req.required,
                priority=req.priority,
                min_sources=req.min_sources,
                max_sources=req.max_sources,
                preferred_paper_types=req.preferred_paper_types,
                preferred_research_designs=req.preferred_research_designs,
                max_age_years=req.max_age_years,
                full_text_required=req.full_text_required,
                min_relevance_score=req.min_relevance_score,
                coverage_weight=req.coverage_weight,
                requirement_meta=req.requirement_meta,
            )
        )

    dependencies = list(
        db.execute(
            select(ResearchPlanDependency)
            .where(ResearchPlanDependency.plan_id == source.id)
        ).scalars()
    )
    for dep in dependencies:
        upstream = section_map.get(dep.upstream_section_id)
        downstream = section_map.get(dep.downstream_section_id)
        if upstream is None or downstream is None:
            continue
        db.add(
            ResearchPlanDependency(
                plan_id=plan.id,
                upstream_section_id=upstream,
                downstream_section_id=downstream,
                dependency_type=dep.dependency_type,
                dependency_meta=dep.dependency_meta,
            )
        )

    db.flush()
    return plan


def save_revision(
    db: Session,
    *,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    body: dict,
) -> ResearchPlan:
    get_project(db, user_id=user_id, project_id=project_id)
    source = db.execute(
        select(ResearchPlan)
        .where(ResearchPlan.project_id == project_id)
        .order_by(ResearchPlan.version.desc())
        .limit(1)
        .with_for_update()
    ).scalar_one_or_none()
    if source is None:
        raise ResearchPlanNotFound()
    return _copy_plan(
        db,
        source=source,
        created_by=user_id,
        status="draft",
        overrides=body,
    )


def restore_version(
    db: Session,
    *,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    target_version: int,
) -> ResearchPlan:
    get_project(db, user_id=user_id, project_id=project_id)
    target = db.execute(
        select(ResearchPlan)
        .where(
            ResearchPlan.project_id == project_id,
            ResearchPlan.version == target_version,
        )
        .limit(1)
        .with_for_update()
    ).scalar_one_or_none()
    if target is None:
        raise ResearchPlanNotFound()
    return _copy_plan(
        db,
        source=target,
        created_by=user_id,
        status="ready",
    )
