"""Immutable-version research plan save/edit service."""
from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import ResearchPlanInvalid, ResearchPlanNotFound
from app.db.models.research_plan import (
    ResearchEvidenceRequirement,
    ResearchPlan,
    ResearchPlanDependency,
    ResearchPlanSection,
)
from app.domain.research_plan import ResearchPlanStatus
from app.schemas.research_plan_mutations import (
    ResearchEvidenceRequirementWrite,
    ResearchPlanDependencyWrite,
    ResearchPlanPatch,
    ResearchPlanSectionWrite,
)


def _context_hash(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _latest_plan(db: Session, *, project_id: uuid.UUID) -> ResearchPlan:
    row = db.execute(
        select(ResearchPlan)
        .where(ResearchPlan.project_id == project_id)
        .order_by(ResearchPlan.version.desc())
        .limit(1)
        .with_for_update()
    ).scalar_one_or_none()
    if row is None:
        raise ResearchPlanNotFound()
    return row


def save_research_plan(
    db: Session,
    *,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    patch: ResearchPlanPatch,
) -> ResearchPlan:
    current = _latest_plan(db, project_id=project_id)
    if patch.expected_version is not None and current.version != patch.expected_version:
        raise ResearchPlanInvalid(
            f"plan version conflict: expected {patch.expected_version}, current {current.version}"
        )

    sections = list(
        db.execute(
            select(ResearchPlanSection)
            .where(ResearchPlanSection.plan_id == current.id)
            .order_by(ResearchPlanSection.display_order.asc())
        ).scalars().all()
    )
    requirements = list(
        db.execute(
            select(ResearchEvidenceRequirement)
            .where(ResearchEvidenceRequirement.plan_id == current.id)
        ).scalars().all()
    )
    dependencies = list(
        db.execute(
            select(ResearchPlanDependency)
            .where(ResearchPlanDependency.plan_id == current.id)
        ).scalars().all()
    )

    next_version = int(
        db.execute(
            select(func.max(ResearchPlan.version)).where(
                ResearchPlan.project_id == project_id
            )
        ).scalar_one() or 0
    ) + 1

    next_values: dict[str, Any] = {
        "research_objective_snapshot": (
            patch.research_objective_snapshot
            if patch.research_objective_snapshot is not None
            else current.research_objective_snapshot
        ),
        "research_questions_snapshot": (
            patch.research_questions_snapshot
            if patch.research_questions_snapshot is not None
            else current.research_questions_snapshot
        ),
        "hypotheses_snapshot": (
            patch.hypotheses_snapshot
            if patch.hypotheses_snapshot is not None
            else current.hypotheses_snapshot
        ),
        "budget": patch.budget if patch.budget is not None else current.budget,
    }

    section_writes: list[ResearchPlanSectionWrite] = patch.sections or []
    if not section_writes and patch.sections is None:
        section_writes = [
            ResearchPlanSectionWrite(
                section_key=s.section_key,
                title=s.title,
                purpose=s.purpose,
                section_type=s.section_type,
                display_order=s.display_order,
                required=s.required,
                word_budget=s.word_budget,
                budget_weight=float(s.budget_weight),
                evidence_coverage_target=float(s.evidence_coverage_target),
                status=s.status,
            )
            for s in sections
        ]

    section_keys = [s.section_key for s in section_writes]
    if len(section_keys) != len(set(section_keys)):
        raise ResearchPlanInvalid("section_key values must be unique")
    orders = [s.display_order for s in section_writes]
    if len(orders) != len(set(orders)):
        raise ResearchPlanInvalid("section display_order values must be unique")
    section_key_set = set(section_keys)

    req_writes: list[ResearchEvidenceRequirementWrite] = patch.evidence_requirements or []
    if patch.evidence_requirements is None:
        old_by_section = {
            s.id: s.section_key for s in sections
        }
        req_writes = [
            ResearchEvidenceRequirementWrite(
                requirement_key=r.requirement_key,
                section_key=old_by_section[r.section_id],
                requirement_type=r.requirement_type,
                description=r.description,
                required=r.required,
                priority=r.priority,
                min_sources=r.min_sources,
                max_sources=r.max_sources,
                preferred_paper_types=r.preferred_paper_types,
                preferred_research_designs=r.preferred_research_designs,
                max_age_years=r.max_age_years,
                full_text_required=r.full_text_required,
                min_relevance_score=(
                    float(r.min_relevance_score)
                    if r.min_relevance_score is not None
                    else None
                ),
                coverage_weight=float(r.coverage_weight),
            )
            for r in requirements
        ]

    dependencies_writes: list[ResearchPlanDependencyWrite] = patch.dependencies or []
    if patch.dependencies is None:
        old_by_id = {s.id: s.section_key for s in sections}
        dependencies_writes = [
            ResearchPlanDependencyWrite(
                upstream_section_key=old_by_id[d.upstream_section_id],
                downstream_section_key=old_by_id[d.downstream_section_id],
                dependency_type=d.dependency_type,
            )
            for d in dependencies
        ]

    for req in req_writes:
        if req.section_key not in section_key_set:
            raise ResearchPlanInvalid(
                f"evidence requirement references unknown section {req.section_key!r}"
            )
        if (
            req.min_sources is not None
            and req.max_sources is not None
            and req.max_sources < req.min_sources
        ):
            raise ResearchPlanInvalid(
                f"max_sources < min_sources for requirement {req.requirement_key!r}"
            )
    for dep in dependencies_writes:
        if (
            dep.upstream_section_key not in section_key_set
            or dep.downstream_section_key not in section_key_set
        ):
            raise ResearchPlanInvalid("dependency references unknown section")
        if dep.upstream_section_key == dep.downstream_section_key:
            raise ResearchPlanInvalid("dependency cannot reference same section")

    serialized = {
        "project_id": str(project_id),
        "base_version": current.version,
        **next_values,
        "sections": [s.model_dump() for s in section_writes],
        "evidence_requirements": [r.model_dump() for r in req_writes],
        "dependencies": [d.model_dump() for d in dependencies_writes],
    }

    current.status = ResearchPlanStatus.SUPERSEDED.value
    plan = ResearchPlan(
        project_id=project_id,
        version=next_version,
        status=ResearchPlanStatus.DRAFT.value,
        planner_version=current.planner_version,
        planning_mode=current.planning_mode,
        context_hash=_context_hash(serialized),
        literature_run_id=current.literature_run_id,
        domain_id=current.domain_id,
        paper_type_code=current.paper_type_code,
        research_design_code=current.research_design_code,
        research_objective_snapshot=next_values["research_objective_snapshot"],
        research_questions_snapshot=next_values["research_questions_snapshot"],
        hypotheses_snapshot=next_values["hypotheses_snapshot"],
        budget=next_values["budget"],
        validation_status="pending",
        validation_errors=None,
        coverage_summary=None,
        completeness_score=None,
        coverage_score=None,
        supersedes_plan_id=current.id,
        created_by=user_id,
    )
    db.add(plan)
    db.flush()

    new_sections: dict[str, ResearchPlanSection] = {}
    for data in section_writes:
        row = ResearchPlanSection(
            plan_id=plan.id,
            section_key=data.section_key,
            title=data.title,
            purpose=data.purpose,
            section_type=data.section_type,
            display_order=data.display_order,
            required=data.required,
            word_budget=data.word_budget,
            budget_weight=data.budget_weight,
            evidence_coverage_target=data.evidence_coverage_target,
            status=data.status,
        )
        db.add(row)
        db.flush()
        new_sections[data.section_key] = row

    for data in req_writes:
        db.add(
            ResearchEvidenceRequirement(
                plan_id=plan.id,
                section_id=new_sections[data.section_key].id,
                requirement_key=data.requirement_key,
                requirement_type=data.requirement_type,
                description=data.description,
                required=data.required,
                priority=data.priority,
                min_sources=data.min_sources,
                max_sources=data.max_sources,
                preferred_paper_types=data.preferred_paper_types,
                preferred_research_designs=data.preferred_research_designs,
                max_age_years=data.max_age_years,
                full_text_required=data.full_text_required,
                min_relevance_score=data.min_relevance_score,
                coverage_weight=data.coverage_weight,
            )
        )

    for data in dependencies_writes:
        db.add(
            ResearchPlanDependency(
                plan_id=plan.id,
                upstream_section_id=new_sections[data.upstream_section_key].id,
                downstream_section_id=new_sections[data.downstream_section_key].id,
                dependency_type=data.dependency_type,
            )
        )

    db.commit()
    db.refresh(plan)
    return plan
