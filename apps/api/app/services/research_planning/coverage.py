"""M24 — Corpus coverage engine."""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.literature import (
    LiteratureIntelligenceRun,
    ProjectLiteratureItem,
)
from app.db.models.source import Source
from app.domain.research_plan import RESEARCH_PLAN_REFERENCE_YEAR


def _is_full_text(source: Source | None) -> bool:
    if source is None:
        return False
    if getattr(source, "extracted_at", None) is not None:
        return True
    status = getattr(source, "status", None)
    return status in ("extracted", "full_text", "structured_full_text")


def _eligible_items(
    db: Session, *, project_id: uuid.UUID
) -> list[tuple[ProjectLiteratureItem, Source | None]]:
    rows = db.execute(
        select(ProjectLiteratureItem, Source)
        .join(
            Source,
            Source.id == ProjectLiteratureItem.source_id,
            isouter=True,
        )
        .where(
            ProjectLiteratureItem.project_id == project_id,
            ProjectLiteratureItem.screening_status.in_(
                ("included", "candidate")
            ),
        )
    ).all()
    return [(r[0], r[1]) for r in rows]


def compute_corpus_coverage(
    db: Session,
    *,
    project_id: uuid.UUID,
    requirements: list,
) -> dict:
    run = db.execute(
        select(LiteratureIntelligenceRun)
        .where(
            LiteratureIntelligenceRun.project_id == project_id,
            LiteratureIntelligenceRun.status == "completed",
        )
        .order_by(
            LiteratureIntelligenceRun.created_at.desc(),
            LiteratureIntelligenceRun.id.desc(),
        )
        .limit(1)
    ).scalar_one_or_none()

    if run is None:
        return {
            "coverage_score": 0.0,
            "coverage_state": "no_literature_run",
            "reference_year": RESEARCH_PLAN_REFERENCE_YEAR,
            "per_requirement": [],
        }

    items = _eligible_items(db, project_id=project_id)
    ref_year = RESEARCH_PLAN_REFERENCE_YEAR

    per_req: list[dict] = []
    total_w = 0.0
    total_ws = 0.0
    for r in requirements:
        baseline = max(1, r.min_sources or 1)
        matching = 0
        for item, source in items:
            if r.preferred_paper_types and (
                item.paper_type_code
                not in (r.preferred_paper_types or [])
            ):
                continue
            if r.preferred_research_designs and (
                item.research_design_code
                not in (r.preferred_research_designs or [])
            ):
                continue
            if r.max_age_years is not None:
                if source is None or source.year is None:
                    continue
                if ref_year - int(source.year) > r.max_age_years:
                    continue
            if r.full_text_required and not _is_full_text(source):
                continue
            if r.min_relevance_score is not None:
                if item.relevance_score is None:
                    continue
                if float(item.relevance_score) < float(
                    r.min_relevance_score
                ):
                    continue
            matching += 1
        score = min(1.0, matching / baseline)
        per_req.append(
            {
                "requirement_key": r.requirement_key,
                "matching_sources": matching,
                "baseline": baseline,
                "score": score,
                "coverage_weight": float(r.coverage_weight),
            }
        )
        total_w += float(r.coverage_weight)
        total_ws += score * float(r.coverage_weight)

    aggregate = (total_ws / total_w) if total_w > 0 else 0.0
    return {
        "coverage_score": aggregate,
        "coverage_state": "computed",
        "reference_year": ref_year,
        "literature_run_id": str(run.id),
        "per_requirement": per_req,
    }
