"""M27 — Deterministic manuscript context hash."""
from __future__ import annotations

import hashlib
import json
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.project import Project
from app.db.models.report import Report
from app.db.models.research_plan import ResearchPlan, ResearchPlanSection
from app.domain.manuscript import (
    MANUSCRIPT_ARCHITECTURE_VERSION,
    MANUSCRIPT_COVERAGE_MODEL_VERSION,
    MANUSCRIPT_INTENT_MAPPING_VERSION,
    MANUSCRIPT_TEMPLATE_VERSION,
)


def _json(value) -> str:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )


def _sha256(parts: list[str]) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(p.encode("utf-8"))
        h.update(b"\x00")
    return h.hexdigest()[:32]


def resolve_ready_plan(
    db: Session, *, project_id: uuid.UUID
) -> ResearchPlan | None:
    return db.execute(
        select(ResearchPlan)
        .where(
            ResearchPlan.project_id == project_id,
            ResearchPlan.status == "ready",
        )
        .order_by(ResearchPlan.version.desc())
        .limit(1)
    ).scalar_one_or_none()


def compute_manuscript_context_hash(
    db: Session,
    *,
    report: Report,
    project: Project,
    plan: ResearchPlan,
) -> str:
    section_keys = [
        s.section_key for s in db.execute(
            select(ResearchPlanSection)
            .where(ResearchPlanSection.plan_id == plan.id)
            .order_by(ResearchPlanSection.display_order.asc())
        ).scalars().all()
    ]

    parts: list[str] = [
        f"arch:{MANUSCRIPT_ARCHITECTURE_VERSION}",
        f"tmpl:{MANUSCRIPT_TEMPLATE_VERSION}",
        f"cov:{MANUSCRIPT_COVERAGE_MODEL_VERSION}",
        f"intent:{MANUSCRIPT_INTENT_MAPPING_VERSION}",
        f"report:{report.id}",
        f"project:{project.id}",
        "report_meta:"
        + _json({
            "topic": report.topic,
            "output_language": report.output_language,
            "tone": report.tone,
            "length": report.length,
            "structure_template": report.structure_template,
            "audience_level": report.audience_level,
        }),
        "project_meta:"
        + _json({
            "research_objective": project.research_objective,
            "research_questions": list(project.research_questions or []),
            "hypotheses": list(project.hypotheses or []),
        }),
        f"plan:{plan.id}",
        f"plan_version:{plan.version}",
        f"plan_context:{plan.context_hash}",
        f"plan_paper_type:{plan.paper_type_code or '-'}",
        f"plan_design:{plan.research_design_code or '-'}",
        f"plan_domain:{plan.domain_id or '-'}",
        "plan_sections:" + _json(section_keys),
    ]
    return _sha256(parts)


__all__ = [
    "resolve_ready_plan",
    "compute_manuscript_context_hash",
]
