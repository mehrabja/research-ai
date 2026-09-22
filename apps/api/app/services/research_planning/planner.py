"""M24 — Research Planning orchestrator."""
from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, replace
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import (
    ResearchPlanGenerationFailed,
    ResearchPlanInvalid,
)
from app.db.models.project import ProjectEvent
from app.db.models.research_plan import (
    ResearchEvidenceRequirement,
    ResearchPlan,
    ResearchPlanDependency,
    ResearchPlanRun,
    ResearchPlanSection,
)
from app.domain.research_plan import (
    RESEARCH_PLAN_VERSION,
    PlanningMode,
    ResearchPlanRunStatus,
    ResearchPlanStatus,
    ValidationStatus,
)
from app.services.projects import get_project
from app.services.research_planning import (
    budget as budget_svc,
)
from app.services.research_planning import (
    context as context_svc,
)
from app.services.research_planning import (
    coverage as coverage_svc,
)
from app.services.research_planning import (
    dependencies as dep_svc,
)
from app.services.research_planning import (
    evidence as evidence_svc,
)
from app.services.research_planning import (
    refinement as refine_svc,
)
from app.services.research_planning import (
    templates as template_svc,
)
from app.services.research_planning import (
    validation as validation_svc,
)

logger = logging.getLogger(__name__)


@dataclass
class PlanningResult:
    plan: ResearchPlan | None
    run: ResearchPlanRun
    skipped: bool
    planning_mode: str


def _lock_project(db: Session, *, project_id: uuid.UUID) -> None:
    db.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:k))"),
        {"k": f"research_plan:{project_id}"},
    )


def _active_ready_plan(
    db: Session, *, project_id: uuid.UUID
) -> ResearchPlan | None:
    return db.execute(
        select(ResearchPlan)
        .where(
            ResearchPlan.project_id == project_id,
            ResearchPlan.status == ResearchPlanStatus.READY.value,
        )
        .order_by(ResearchPlan.version.desc())
        .limit(1)
    ).scalar_one_or_none()


def _next_version(db: Session, *, project_id: uuid.UUID) -> int:
    cur = db.execute(
        select(func.coalesce(func.max(ResearchPlan.version), 0)).where(
            ResearchPlan.project_id == project_id
        )
    ).scalar_one()
    return int(cur) + 1


def _completed_run(
    db: Session, *, project_id: uuid.UUID,
    context_hash: str, planner_version: str,
) -> ResearchPlanRun | None:
    return db.execute(
        select(ResearchPlanRun)
        .where(
            ResearchPlanRun.project_id == project_id,
            ResearchPlanRun.context_hash == context_hash,
            ResearchPlanRun.planner_version == planner_version,
            ResearchPlanRun.status
            == ResearchPlanRunStatus.COMPLETED.value,
        )
    ).scalar_one_or_none()


def _emit_event(
    db: Session, *, project_id: uuid.UUID,
    user_id: uuid.UUID | None, event_type: str,
    meta: dict[str, Any],
) -> None:
    db.add(ProjectEvent(
        project_id=project_id,
        user_id=user_id,
        event_type=event_type,
        event_meta=meta,
    ))


def _llm_available(settings) -> bool:
    if not getattr(settings, "research_plan_enabled", True):
        return False
    if getattr(settings, "research_plan_llm_required", False):
        return True
    provider = getattr(settings, "generation_provider", "openai")
    if provider == "openai":
        return bool(getattr(settings, "generation_openai_api_key", ""))
    return False


def _make_llm_provider(settings):
    """Build the LLM provider used for plan refinement.

    The OpenAI provider requires an explicit model + api_key. We
    reuse M12 settings; if the class signature changes, this is the
    single place to adjust.
    """
    from app.integrations.generation.openai import (
        OpenAIGenerationProvider,
    )
    return OpenAIGenerationProvider(
        api_key=settings.generation_openai_api_key,
        model=settings.generation_model,
    )


class _SectionView:
    __slots__ = (
        "section_key", "title", "purpose", "display_order",
        "required", "word_budget",
    )

    def __init__(self, key, title, purpose, order, required, wb):
        self.section_key = key
        self.title = title
        self.purpose = purpose
        self.display_order = order
        self.required = required
        self.word_budget = wb


class _ReqView:
    __slots__ = ("requirement_key", "section_key")

    def __init__(self, key, section_key):
        self.requirement_key = key
        self.section_key = section_key


def generate_research_plan(
    db: Session,
    *,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
    force: bool = False,
    commit: bool = True,
) -> PlanningResult:
    started = time.perf_counter()
    context_hash: str | None = None
    settings = get_settings()

    project = get_project(db, user_id=user_id, project_id=project_id)
    if project.status == "archived":
        raise ResearchPlanGenerationFailed("project is archived")

    try:
        _lock_project(db, project_id=project_id)
        context_hash = context_svc.compute_research_planning_hash(
            db, project_id=project_id
        )

        existing_run = _completed_run(
            db, project_id=project_id,
            context_hash=context_hash,
            planner_version=RESEARCH_PLAN_VERSION,
        )
        if existing_run is not None:
            duration_ms = int((time.perf_counter() - started) * 1000)
            run = ResearchPlanRun(
                project_id=project_id,
                plan_id=existing_run.plan_id,
                context_hash=context_hash,
                planner_version=RESEARCH_PLAN_VERSION,
                status=ResearchPlanRunStatus.SKIPPED.value,
                planning_mode=existing_run.planning_mode,
                duration_ms=duration_ms,
            )
            db.add(run)
            _emit_event(
                db, project_id=project_id, user_id=user_id,
                event_type="research_plan_generation_skipped",
                meta={
                    "context_hash": context_hash,
                    "planner_version": RESEARCH_PLAN_VERSION,
                    "force": bool(force),
                    "reason": (
                        "force_ignored_duplicate" if force
                        else "context_unchanged"
                    ),
                    "duration_ms": duration_ms,
                },
            )
            if commit:
                db.commit()
                db.refresh(run)
            else:
                db.flush()
            plan = (
                db.get(ResearchPlan, existing_run.plan_id)
                if existing_run.plan_id else None
            )
            return PlanningResult(
                plan=plan, run=run, skipped=True,
                planning_mode=existing_run.planning_mode,
            )

        _emit_event(
            db, project_id=project_id, user_id=user_id,
            event_type="research_plan_generation_started",
            meta={
                "context_hash": context_hash,
                "planner_version": RESEARCH_PLAN_VERSION,
            },
        )

        snap = context_svc.build_research_planning_context(
            db, project_id=project_id
        )
        classification = snap["classification"]
        paper_type_code = (
            classification.paper_type_code if classification else None
        )
        design_code = (
            classification.research_design_code if classification else None
        )

        template = template_svc.select_template(paper_type_code)

        section_weights = {
            s.key: s.default_word_weight for s in template.sections
        }
        budget = budget_svc.build_default_budget(
            section_weights=section_weights,
            word_target=settings.research_plan_default_word_target,
        )

        req_drafts = evidence_svc.build_evidence_requirements(
            template=template,
            paper_type_code=paper_type_code,
            research_design_code=design_code,
            gaps=snap["gaps"],
            clusters=snap["clusters"],
        )

        section_keys = [s.key for s in template.sections]
        dep_edges = dep_svc.section_dependency_template(section_keys)
        dep_svc.validate_dependency_graph(section_keys, dep_edges)

        # ---------- Optional LLM refinement ----------
        planning_mode = PlanningMode.DETERMINISTIC.value
        llm_provider: str | None = None
        llm_model: str | None = None
        section_dicts: list[dict[str, Any]] = [
            {
                "section_key": st.key,
                "title": st.title,
                "purpose": st.purpose,
            }
            for st in template.sections
        ]
        req_dicts: list[dict[str, Any]] = [
            {
                "requirement_key": d.requirement_key,
                "description": d.description,
                "priority": d.priority,
            }
            for d in req_drafts
        ]

        if settings.research_plan_enabled and _llm_available(settings):
            try:
                provider = _make_llm_provider(settings)
                prompt = refine_svc.build_refinement_prompt(
                    paper_type_code=paper_type_code,
                    research_design_code=design_code,
                    research_objective=(
                        snap["project"].research_objective
                        if snap["project"] else None
                    ),
                    research_questions=(
                        snap["project"].research_questions
                        if snap["project"] else None
                    ),
                    hypotheses=(
                        snap["project"].hypotheses
                        if snap["project"] else None
                    ),
                    template_section_keys=section_keys,
                    template_requirement_keys=[
                        d.requirement_key for d in req_drafts
                    ],
                )
                raw = refine_svc.call_refinement_provider(
                    provider, prompt
                )
                allowed_sections = set(section_keys)
                allowed_reqs = {d.requirement_key for d in req_drafts}
                ref = refine_svc.parse_and_validate_refinement(
                    raw=raw,
                    allowed_section_keys=allowed_sections,
                    allowed_requirement_keys=allowed_reqs,
                )
                if ref is None:
                    planning_mode = (
                        PlanningMode.DETERMINISTIC_FALLBACK.value
                    )
                else:
                    section_dicts = (
                        refine_svc.apply_refinement_to_sections(
                            sections=section_dicts, refinement=ref,
                        )
                    )
                    req_dicts = (
                        refine_svc.apply_refinement_to_requirements(
                            requirements=req_dicts, refinement=ref,
                        )
                    )
                    if ref.budget_adjustments:
                        budget = budget_svc.apply_budget_adjustments(
                            budget, ref.budget_adjustments
                        )
                    planning_mode = PlanningMode.HYBRID.value
                    llm_provider = getattr(
                        settings, "generation_provider", None
                    )
                    llm_model = getattr(
                        settings, "generation_model", None
                    )
            except Exception:  # noqa: BLE001
                logger.exception(
                    "research_plan_llm_refinement_failed"
                )
                planning_mode = (
                    PlanningMode.DETERMINISTIC_FALLBACK.value
                )
                if settings.research_plan_llm_required:
                    raise
        # ---------- /LLM refinement ----------

        # Apply refinements back onto frozen drafts via dataclasses.replace
        desc_by_key: dict[str, str | None] = {
            str(r["requirement_key"]): r.get("description")
            for r in req_dicts
        }
        pri_by_key: dict[str, int] = {
            str(r["requirement_key"]): int(r["priority"])
            for r in req_dicts
            if r.get("priority") is not None
        }
        new_drafts: list[evidence_svc.EvidenceRequirementDraft] = []
        for d in req_drafts:
            updates: dict[str, Any] = {}
            desc = desc_by_key.get(d.requirement_key)
            if desc:
                updates["description"] = desc
            pri = pri_by_key.get(d.requirement_key)
            if pri is not None:
                updates["priority"] = pri
            new_drafts.append(
                replace(d, **updates) if updates else d
            )
        req_drafts = new_drafts

        wb_by = budget["word_budget_by_section"]
        title_by_key = {s["section_key"]: s for s in section_dicts}

        sections_for_validation = []
        for i, st in enumerate(template.sections):
            row = title_by_key.get(st.key, {})
            title = row.get("title") or st.title
            purpose = row.get("purpose") or st.purpose
            sections_for_validation.append(
                _SectionView(
                    st.key, title, purpose, i,
                    st.required, wb_by.get(st.key, 0),
                )
            )

        vres = validation_svc.validate_plan_structure(
            sections=sections_for_validation,
            requirements=[
                _ReqView(d.requirement_key, d.section_key)
                for d in req_drafts
            ],
            budget=budget,
            dependency_edges=dep_edges,
            plan_section_key_of=lambda s: s.section_key,
            category_resolved=classification is not None,
        )
        if not vres.valid():
            raise ResearchPlanInvalid(
                "invalid plan structure: " + "; ".join(vres.errors)
            )

        try:
            cov = coverage_svc.compute_corpus_coverage(
                db, project_id=project_id, requirements=req_drafts
            )
        except Exception:
            logger.exception("coverage computation failed")
            cov = {
                "coverage_score": 0.0,
                "coverage_state": "error",
                "per_requirement": [],
            }

        next_version = _next_version(db, project_id=project_id)
        prev_active = _active_ready_plan(db, project_id=project_id)

        plan = ResearchPlan(
            project_id=project_id,
            version=next_version,
            status=ResearchPlanStatus.DRAFT.value,
            planner_version=RESEARCH_PLAN_VERSION,
            planning_mode=planning_mode,
            context_hash=context_hash,
            literature_run_id=(
                snap["literature_run"].id
                if snap["literature_run"] else None
            ),
            domain_id=(
                classification.domain_id if classification else None
            ),
            paper_type_code=paper_type_code,
            research_design_code=design_code,
            research_objective_snapshot=(
                snap["project"].research_objective
                if snap["project"] else None
            ),
            research_questions_snapshot=(
                snap["project"].research_questions
                if snap["project"] else None
            ),
            hypotheses_snapshot=(
                snap["project"].hypotheses if snap["project"] else None
            ),
            budget=budget,
            completeness_score=vres.score,
            coverage_score=cov["coverage_score"],
            validation_status=ValidationStatus.VALID.value,
            validation_errors=[],
            coverage_summary=cov,
            supersedes_plan_id=(
                prev_active.id if prev_active else None
            ),
            created_by=user_id,
        )
        db.add(plan)
        db.flush()

        section_by_key: dict[str, ResearchPlanSection] = {}
        for i, st in enumerate(template.sections):
            row = title_by_key.get(st.key, {})
            title = row.get("title") or st.title
            purpose = row.get("purpose") or st.purpose
            s = ResearchPlanSection(
                plan_id=plan.id,
                section_key=st.key,
                title=title,
                purpose=purpose,
                section_type=st.section_type,
                display_order=i,
                required=st.required,
                word_budget=wb_by.get(st.key, 0),
                budget_weight=budget["section_allocations"].get(
                    st.key, 0.0
                ),
                evidence_coverage_target=0.5,
                status="active",
            )
            db.add(s)
            section_by_key[st.key] = s
        db.flush()

        for d in req_drafts:
            sec = section_by_key.get(d.section_key)
            if sec is None:
                continue
            db.add(ResearchEvidenceRequirement(
                plan_id=plan.id,
                section_id=sec.id,
                requirement_key=d.requirement_key,
                requirement_type=d.requirement_type,
                description=d.description,
                required=d.required,
                priority=d.priority,
                min_sources=d.min_sources,
                max_sources=d.max_sources,
                preferred_paper_types=d.preferred_paper_types,
                preferred_research_designs=(
                    d.preferred_research_designs
                ),
                max_age_years=d.max_age_years,
                full_text_required=d.full_text_required,
                min_relevance_score=d.min_relevance_score,
                coverage_weight=d.coverage_weight,
                requirement_meta=d.meta or None,
            ))

        for up, down in dep_edges:
            db.add(ResearchPlanDependency(
                plan_id=plan.id,
                upstream_section_id=section_by_key[up].id,
                downstream_section_id=section_by_key[down].id,
                dependency_type="requires",
            ))

        if prev_active is not None:
            prev_active.status = ResearchPlanStatus.SUPERSEDED.value
            db.flush()

        plan.status = ResearchPlanStatus.READY.value
        db.flush()

        duration_ms = int((time.perf_counter() - started) * 1000)
        run = ResearchPlanRun(
            project_id=project_id,
            plan_id=plan.id,
            context_hash=context_hash,
            planner_version=RESEARCH_PLAN_VERSION,
            status=ResearchPlanRunStatus.COMPLETED.value,
            planning_mode=planning_mode,
            llm_provider=llm_provider,
            llm_model=llm_model,
            input_snapshot={
                "version": RESEARCH_PLAN_VERSION,
                "literature_run_id": (
                    str(snap["literature_run"].id)
                    if snap["literature_run"] else None
                ),
            },
            output_summary={
                "sections": len(template.sections),
                "requirements": len(req_drafts),
                "version": next_version,
                "coverage_score": cov["coverage_score"],
                "planning_mode": planning_mode,
            },
            duration_ms=duration_ms,
        )
        db.add(run)
        db.flush()

        _emit_event(
            db, project_id=project_id, user_id=user_id,
            event_type="research_plan_generation_completed",
            meta={
                "plan_id": str(plan.id),
                "context_hash": context_hash,
                "planner_version": RESEARCH_PLAN_VERSION,
                "planning_mode": planning_mode,
                "duration_ms": duration_ms,
            },
        )

        if commit:
            db.commit()
            db.refresh(plan)
            db.refresh(run)
        else:
            db.flush()
        return PlanningResult(
            plan=plan, run=run, skipped=False,
            planning_mode=planning_mode,
        )

    except Exception as exc:
        logger.exception("research_plan_generation_failed")
        duration_ms = int((time.perf_counter() - started) * 1000)
        try:
            db.rollback()
        except Exception:  # noqa: BLE001
            logger.exception("research_plan_rollback_failed")
        try:
            db.add(ResearchPlanRun(
                project_id=project_id,
                plan_id=None,
                context_hash=context_hash or "-",
                planner_version=RESEARCH_PLAN_VERSION,
                status=ResearchPlanRunStatus.FAILED.value,
                planning_mode=PlanningMode.DETERMINISTIC.value,
                error_message=str(exc)[:500],
                duration_ms=duration_ms,
            ))
            _emit_event(
                db, project_id=project_id, user_id=user_id,
                event_type="research_plan_generation_failed",
                meta={
                    "context_hash": context_hash or "-",
                    "planner_version": RESEARCH_PLAN_VERSION,
                    "error": str(exc)[:200],
                    "duration_ms": duration_ms,
                },
            )
            if commit:
                db.commit()
        except Exception:
            logger.exception("research_plan_failure_persist_failed")
            if commit:
                db.rollback()
        raise
