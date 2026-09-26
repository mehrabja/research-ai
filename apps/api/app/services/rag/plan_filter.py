"""M26 — Research plan (M24) aware filtering.

Stage A already resolved the requirement through the retrieval
context. This module only applies requirement constraints to
already-generated candidates. It never resolves plan/section/
requirement.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.literature import ProjectLiteratureItem
from app.db.models.research_plan import (
    ResearchEvidenceRequirement,
    ResearchPlan,
    ResearchPlanSection,
)
from app.db.models.source import Source
from app.domain.research_plan import RESEARCH_PLAN_REFERENCE_YEAR
from app.services.rag.candidates import Candidate

_SCREENING_INCLUDED = frozenset({"candidate", "included"})
_FULL_TEXT_STATUSES = frozenset(
    {"extracted", "full_text", "structured_full_text"}
)


@dataclass(frozen=True)
class PlanFilterResult:
    candidates: list[Candidate]
    warnings: list[str]
    rejected_counts: dict[str, int]
    distinct_source_count: int
    min_sources_satisfied: bool


def count_distinct_sources(candidates: list[Candidate]) -> int:
    return len({c.source_id for c in candidates})


def _is_full_text_available(source: Source | None) -> bool:
    if source is None:
        return False
    if source.extracted_at is not None:
        return True
    return (source.status or "").lower() in _FULL_TEXT_STATUSES


def _matches_code_set(
    value: str | None, allowed: list | tuple | None
) -> bool:
    if not allowed:
        return True
    if value is None:
        return False
    normalized = {str(x) for x in allowed}
    return value in normalized


def resolve_plan_context(
    db: Session,
    *,
    project_id: uuid.UUID,
    section_id: uuid.UUID | None,
    requirement_id: uuid.UUID | None,
) -> tuple[
    ResearchPlan | None,
    ResearchPlanSection | None,
    ResearchEvidenceRequirement | None,
]:
    """Kept for backward compat. Stage A resolves via context.py."""
    plan = db.execute(
        select(ResearchPlan)
        .where(
            ResearchPlan.project_id == project_id,
            ResearchPlan.status == "ready",
        )
        .order_by(ResearchPlan.version.desc())
        .limit(1)
    ).scalar_one_or_none()

    section: ResearchPlanSection | None = None
    if section_id is not None:
        section = db.execute(
            select(ResearchPlanSection).where(
                ResearchPlanSection.id == section_id
            )
        ).scalar_one_or_none()

    requirement: ResearchEvidenceRequirement | None = None
    if requirement_id is not None:
        requirement = db.execute(
            select(ResearchEvidenceRequirement).where(
                ResearchEvidenceRequirement.id == requirement_id
            )
        ).scalar_one_or_none()

    return plan, section, requirement


def apply_plan_filters(
    candidates: list[Candidate],
    *,
    min_year: int | None,
    max_year: int | None,
    required_full_text: bool,
    sources_by_id: dict,
) -> tuple[list[Candidate], list[str]]:
    warnings: list[str] = []
    if not (min_year or max_year or required_full_text):
        return candidates, warnings

    kept: list[Candidate] = []
    dropped_year = 0
    dropped_full_text = 0

    for c in candidates:
        src = sources_by_id.get(c.source_id)
        if src is None:
            kept.append(c)
            continue
        if min_year is not None and (src.year or 0) < min_year:
            dropped_year += 1
            continue
        if max_year is not None and (src.year or 9999) > max_year:
            dropped_year += 1
            continue
        if (
            required_full_text
            and not _is_full_text_available(src)
        ):
            dropped_full_text += 1
            continue
        kept.append(c)

    if dropped_year:
        warnings.append(f"filtered_by_year: {dropped_year}")
    if dropped_full_text:
        warnings.append(f"filtered_by_full_text: {dropped_full_text}")
    return kept, warnings


def apply_requirement_filter(
    candidates: list[Candidate],
    *,
    requirement: ResearchEvidenceRequirement | None,
    sources_by_id: dict[uuid.UUID, Source],
    literature_by_source_id: dict[
        uuid.UUID, ProjectLiteratureItem
    ],
) -> PlanFilterResult:
    """Apply M24 requirement constraints to candidates.

    Candidate-level filters only. ``min_sources`` is a threshold
    outcome, not a candidate filter — it never deletes candidates.
    """
    warnings: list[str] = []
    rejected: dict[str, int] = {
        "paper_type": 0,
        "research_design": 0,
        "max_age": 0,
        "full_text": 0,
        "min_relevance": 0,
        "screening_status": 0,
    }

    if requirement is None:
        distinct = count_distinct_sources(candidates)
        return PlanFilterResult(
            candidates=candidates,
            warnings=warnings,
            rejected_counts={},
            distinct_source_count=distinct,
            min_sources_satisfied=True,
        )

    preferred_pt = requirement.preferred_paper_types
    preferred_rd = requirement.preferred_research_designs
    max_age = requirement.max_age_years
    min_rel = requirement.min_relevance_score
    full_text_required = bool(requirement.full_text_required)

    kept: list[Candidate] = []
    for c in candidates:
        src = sources_by_id.get(c.source_id)
        lit = literature_by_source_id.get(c.source_id)

        if (
            lit is not None
            and lit.screening_status not in _SCREENING_INCLUDED
        ):
            rejected["screening_status"] += 1
            continue

        if preferred_pt and (
            lit is None
            or not _matches_code_set(lit.paper_type_code, preferred_pt)
        ):
            rejected["paper_type"] += 1
            continue

        if preferred_rd and (
            lit is None
            or not _matches_code_set(
                lit.research_design_code, preferred_rd
            )
        ):
            rejected["research_design"] += 1
            continue

        if min_rel is not None:
            if lit is None or lit.relevance_score is None:
                rejected["min_relevance"] += 1
                continue
            if float(lit.relevance_score) < float(min_rel):
                rejected["min_relevance"] += 1
                continue

        if max_age is not None:
            if src is None or src.year is None:
                rejected["max_age"] += 1
                continue
            if (
                RESEARCH_PLAN_REFERENCE_YEAR - src.year
            ) > max_age:
                rejected["max_age"] += 1
                continue

        if (
            full_text_required
            and not _is_full_text_available(src)
        ):
            rejected["full_text"] += 1
            continue

        kept.append(c)

    for key, count in rejected.items():
        if count > 0:
            warnings.append(f"requirement_filtered_{key}: {count}")

    distinct = count_distinct_sources(kept)
    min_sources = requirement.min_sources
    min_satisfied = True
    if (
        min_sources is not None
        and min_sources > 0
        and distinct < min_sources
    ):
        min_satisfied = False
        warnings.append(
            "requirement_min_sources_unsatisfied: "
            f"required={min_sources} got={distinct}"
        )

    rejected_nonzero = {
        k: v for k, v in rejected.items() if v > 0
    }

    return PlanFilterResult(
        candidates=kept,
        warnings=warnings,
        rejected_counts=rejected_nonzero,
        distinct_source_count=distinct,
        min_sources_satisfied=min_satisfied,
    )


__all__ = [
    "PlanFilterResult",
    "apply_plan_filters",
    "apply_requirement_filter",
    "count_distinct_sources",
    "resolve_plan_context",
]
