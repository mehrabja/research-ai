"""M27 — Manuscript architecture builder (deterministic orchestrator)."""
from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import (
    ManuscriptConfigurationInvalid,
    ManuscriptGenerationFailed,
    ManuscriptInvalid,
    ManuscriptResearchPlanMissing,
    ManuscriptUnmappedRequirement,
)
from app.db.models.manuscript import (
    Manuscript,
    ManuscriptRun,
    ManuscriptSection,
    ManuscriptSectionDependency,
    ManuscriptVersion,
)
from app.db.models.report import Report
from app.db.models.research_plan import (
    ResearchEvidenceRequirement,
    ResearchPlan,
    ResearchPlanDependency,
    ResearchPlanSection,
)
from app.domain.manuscript import (
    MANUSCRIPT_ARCHITECTURE_VERSION,
    MANUSCRIPT_TEMPLATE_VERSION,
    ManuscriptRunStatus,
    ManuscriptStatus,
    ManuscriptVersionStatus,
)
from app.services.manuscript import context as ctx_svc
from app.services.manuscript import mapping as map_svc
from app.services.manuscript.ordering import topological_research_order
from app.services.projects import get_project
from app.services.reports import get_report

logger = logging.getLogger(__name__)


@dataclass
class ManuscriptBuildResult:
    manuscript: Manuscript | None
    version: ManuscriptVersion | None
    run: ManuscriptRun
    skipped: bool
    sections: list[ManuscriptSection]


def _lock_report(db: Session, *, report_id: uuid.UUID) -> None:
    db.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:k))"),
        {"k": f"manuscript:{report_id}"},
    )


def _completed_run(
    db: Session, *, report_id: uuid.UUID, context_hash: str
) -> ManuscriptRun | None:
    return db.execute(
        select(ManuscriptRun).where(
            ManuscriptRun.report_id == report_id,
            ManuscriptRun.context_hash == context_hash,
            ManuscriptRun.architecture_version
            == MANUSCRIPT_ARCHITECTURE_VERSION,
            ManuscriptRun.status == ManuscriptRunStatus.COMPLETED.value,
        )
    ).scalar_one_or_none()


def _next_version(db: Session, *, manuscript_id: uuid.UUID) -> int:
    cur = db.execute(
        select(func.coalesce(func.max(ManuscriptVersion.version), 0))
        .where(ManuscriptVersion.manuscript_id == manuscript_id)
    ).scalar_one()
    return int(cur) + 1


def _build_title(
    *, report: Report, plan: ResearchPlan, project
) -> tuple[str, str]:
    base = (report.topic or "").strip() or "Untitled Manuscript"
    if len(base) > 240:
        base = base[:237].rstrip() + "..."
    rationale = (
        f"derived from report.topic; "
        f"paper_type={plan.paper_type_code or '-'}; "
        f"design={plan.research_design_code or '-'}"
    )
    return base, rationale


def _build_abstract_direction(
    *, plan: ResearchPlan, project
) -> dict[str, Any]:
    objective = plan.research_objective_snapshot or (
        project.research_objective if project else None
    )
    return {
        "problem": objective or "TBD",
        "objective": objective or "TBD",
        "method": f"paper_type={plan.paper_type_code or '-'}",
        "expected_findings_direction": "from results section evidence",
        "contribution": "from conclusion section synthesis",
    }


def _select_reqs_for_plan(
    db: Session, *, plan: ResearchPlan
) -> tuple[
    list[ResearchPlanSection],
    list[ResearchEvidenceRequirement],
    list[ResearchPlanDependency],
]:
    sections = list(db.execute(
        select(ResearchPlanSection)
        .where(ResearchPlanSection.plan_id == plan.id)
        .order_by(ResearchPlanSection.display_order.asc())
    ).scalars().all())
    reqs = list(db.execute(
        select(ResearchEvidenceRequirement)
        .where(ResearchEvidenceRequirement.plan_id == plan.id)
    ).scalars().all())
    deps = list(db.execute(
        select(ResearchPlanDependency)
        .where(ResearchPlanDependency.plan_id == plan.id)
    ).scalars().all())

    section_ids = {s.id for s in sections}
    for r in reqs:
        if r.section_id not in section_ids:
            raise ManuscriptInvalid(
                f"evidence requirement {r.id} references foreign section"
            )
    for d in deps:
        if d.upstream_section_id not in section_ids:
            raise ManuscriptInvalid(
                f"dependency {d.id} has foreign upstream"
            )
        if d.downstream_section_id not in section_ids:
            raise ManuscriptInvalid(
                f"dependency {d.id} has foreign downstream"
            )
    return sections, reqs, deps


def generate_manuscript(
    db: Session,
    *,
    user_id: uuid.UUID,
    report_id: uuid.UUID,
    force: bool = False,
    commit: bool = True,
) -> ManuscriptBuildResult:
    started = time.perf_counter()
    context_hash: str | None = None
    settings = get_settings()

    if not getattr(settings, "manuscript_enabled", True):
        raise ManuscriptConfigurationInvalid("manuscript is disabled")

    report = get_report(db, user_id=user_id, report_id=report_id)
    if report.project_id is None:
        raise ManuscriptGenerationFailed(
            "report is not attached to a project"
        )
    project = get_project(
        db, user_id=user_id, project_id=report.project_id
    )
    if project.status == "archived":
        raise ManuscriptGenerationFailed("project is archived")

    try:
        _lock_report(db, report_id=report_id)

        plan = ctx_svc.resolve_ready_plan(db, project_id=project.id)
        if plan is None:
            raise ManuscriptResearchPlanMissing()

        context_hash = ctx_svc.compute_manuscript_context_hash(
            db, report=report, project=project, plan=plan
        )

        existing = _completed_run(
            db, report_id=report_id, context_hash=context_hash
        )
        if existing is not None:
            duration_ms = int((time.perf_counter() - started) * 1000)
            run = ManuscriptRun(
                report_id=report_id,
                manuscript_id=existing.manuscript_id,
                manuscript_version_id=existing.manuscript_version_id,
                context_hash=context_hash,
                architecture_version=MANUSCRIPT_ARCHITECTURE_VERSION,
                status=ManuscriptRunStatus.SKIPPED.value,
                duration_ms=duration_ms,
                output_summary={
                    "reason": "context_unchanged",
                    "force_requested": bool(force),
                },
            )
            db.add(run)
            if commit:
                db.commit()
                db.refresh(run)
            else:
                db.flush()
            ms = (
                db.get(Manuscript, existing.manuscript_id)
                if existing.manuscript_id else None
            )
            ver = (
                db.get(ManuscriptVersion, existing.manuscript_version_id)
                if existing.manuscript_version_id else None
            )
            return ManuscriptBuildResult(
                manuscript=ms, version=ver, run=run, skipped=True,
                sections=[],
            )

        sections, reqs, deps = _select_reqs_for_plan(db, plan=plan)

        budget = plan.budget or {}
        wb_by_section = budget.get("word_budget_by_section") or {}
        word_target = int(budget.get("word_target") or 0)

        snaps, warnings = map_svc.build_section_snapshots(
            plan=plan,
            sections=sections,
            requirements=reqs,
            word_budget_by_section=wb_by_section,
        )
        edges_raw = map_svc.extract_dependency_edges(
            sections=sections, deps=deps
        )

        total_words = sum(int(s.word_budget) for s in snaps)
        if word_target > 0:
            diff = abs(total_words - word_target) / word_target
            tol = float(
                getattr(settings, "manuscript_budget_tolerance", 0.10)
            )
            if diff > tol:
                raise ManuscriptInvalid(
                    f"budget sum {total_words} differs from "
                    f"word_target {word_target} by {diff:.2%}"
                )

        for s in snaps:
            for r in s.requirements:
                if r.required and not r.retrieval_intents:
                    raise ManuscriptUnmappedRequirement(
                        f"{s.section_key}:{r.requirement_key}"
                    )

        title, rationale = _build_title(
            report=report, plan=plan, project=project
        )
        abstract_direction = _build_abstract_direction(
            plan=plan, project=project
        )

        ms = db.execute(
            select(Manuscript).where(Manuscript.report_id == report_id)
        ).scalar_one_or_none()
        if ms is None:
            ms = Manuscript(
                report_id=report_id,
                status=ManuscriptStatus.DRAFT.value,
                architecture_version=MANUSCRIPT_ARCHITECTURE_VERSION,
                template_version=MANUSCRIPT_TEMPLATE_VERSION,
                context_hash=context_hash,
                created_by=user_id,
            )
            db.add(ms)
            db.flush()

        next_ver = _next_version(db, manuscript_id=ms.id)

        version = ManuscriptVersion(
            manuscript_id=ms.id,
            version=next_ver,
            status=ManuscriptVersionStatus.DRAFT.value,
            architecture_version=MANUSCRIPT_ARCHITECTURE_VERSION,
            template_version=MANUSCRIPT_TEMPLATE_VERSION,
            research_plan_id=plan.id,
            research_plan_version=int(plan.version),
            research_plan_context_hash=plan.context_hash,
            context_hash=context_hash,
            title=title,
            title_rationale=rationale,
            abstract_direction=abstract_direction,
            word_target=word_target,
            architecture_meta={
                "intent_mapping_version": "m27-intent-v1",
                "paper_type_code": plan.paper_type_code,
                "research_design_code": plan.research_design_code,
            },
            created_by=user_id,
        )
        db.add(version)
        db.flush()

        section_rows: dict[str, ManuscriptSection] = {}
        for s in snaps:
            contract = map_svc.build_research_contract(s)
            row = ManuscriptSection(
                manuscript_version_id=version.id,
                source_research_plan_section_id=uuid.UUID(
                    s.source_plan_section_id
                ),
                section_key=s.section_key,
                title=s.title,
                purpose=s.purpose,
                section_type=s.section_type,
                display_order=s.display_order,
                required=s.required,
                word_budget=s.word_budget,
                budget_weight=s.budget_weight,
                evidence_coverage_target=s.evidence_coverage_target,
                research_objective=contract["research_objective"],
                writing_objective=s.purpose,
                citation_required=bool(contract["citation_required"]),
                research_contract=contract,
                status="active",
            )
            db.add(row)
            section_rows[s.section_key] = row
        db.flush()

        for up, down, dep_type in edges_raw:
            db.add(ManuscriptSectionDependency(
                manuscript_version_id=version.id,
                upstream_section_id=section_rows[up].id,
                downstream_section_id=section_rows[down].id,
                dependency_type=dep_type,
            ))

        version.sections_snapshot = [s.as_dict() for s in snaps]

        if ms.current_version_id is not None:
            prev = db.get(ManuscriptVersion, ms.current_version_id)
            if prev is not None and prev.id != version.id:
                prev.status = ManuscriptVersionStatus.SUPERSEDED.value

        version.status = ManuscriptVersionStatus.READY.value
        ms.current_version_id = version.id
        ms.status = ManuscriptStatus.READY.value
        ms.context_hash = context_hash
        db.flush()

        duration_ms = int((time.perf_counter() - started) * 1000)
        research_order = topological_research_order(
            section_keys=[s.section_key for s in snaps],
            edges=[(u, d) for u, d, _ in edges_raw],
        )
        run = ManuscriptRun(
            report_id=report_id,
            manuscript_id=ms.id,
            manuscript_version_id=version.id,
            context_hash=context_hash,
            architecture_version=MANUSCRIPT_ARCHITECTURE_VERSION,
            status=ManuscriptRunStatus.COMPLETED.value,
            input_snapshot={
                "report_id": str(report_id),
                "project_id": str(project.id),
                "research_plan_id": str(plan.id),
                "research_plan_version": int(plan.version),
            },
            output_summary={
                "version": next_ver,
                "section_count": len(snaps),
                "requirement_count": sum(len(s.requirements) for s in snaps),
                "research_order": research_order,
                "research_plan_version": int(plan.version),
                "architecture_version": MANUSCRIPT_ARCHITECTURE_VERSION,
                "template_version": MANUSCRIPT_TEMPLATE_VERSION,
            },
            warnings=warnings,
            duration_ms=duration_ms,
        )
        db.add(run)
        db.flush()

        if commit:
            db.commit()
            db.refresh(ms)
            db.refresh(version)
            db.refresh(run)
        else:
            db.flush()

        return ManuscriptBuildResult(
            manuscript=ms,
            version=version,
            run=run,
            skipped=False,
            sections=list(section_rows.values()),
        )

    except Exception as exc:
        logger.exception("manuscript_generation_failed")
        duration_ms = int((time.perf_counter() - started) * 1000)
        try:
            db.rollback()
        except Exception:
            logger.exception("manuscript_rollback_failed")
        try:
            db.add(ManuscriptRun(
                report_id=report_id,
                context_hash=context_hash or "-",
                architecture_version=MANUSCRIPT_ARCHITECTURE_VERSION,
                status=ManuscriptRunStatus.FAILED.value,
                error_message=str(exc)[:500],
                duration_ms=duration_ms,
            ))
            if commit:
                db.commit()
        except Exception:
            logger.exception("manuscript_failure_persist_failed")
            if commit:
                db.rollback()
        raise


__all__ = ["ManuscriptBuildResult", "generate_manuscript"]
