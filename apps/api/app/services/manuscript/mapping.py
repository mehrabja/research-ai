"""M27 — M24 → M27 deterministic mapping."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.db.models.research_plan import (
    ResearchEvidenceRequirement,
    ResearchPlan,
    ResearchPlanDependency,
    ResearchPlanSection,
)
from app.domain.manuscript import (
    MANUSCRIPT_INTENT_MAPPING_VERSION,
    citation_required_for,
    map_requirement_type_to_intents,
)


@dataclass(frozen=True)
class RequirementSnapshot:
    requirement_id: str
    requirement_key: str
    requirement_type: str
    required: bool
    priority: int
    min_sources: int | None
    max_sources: int | None
    preferred_paper_types: list[str]
    preferred_research_designs: list[str]
    max_age_years: int | None
    full_text_required: bool
    min_relevance_score: float | None
    coverage_weight: float
    retrieval_intents: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "requirement_id": self.requirement_id,
            "requirement_key": self.requirement_key,
            "requirement_type": self.requirement_type,
            "required": self.required,
            "priority": self.priority,
            "min_sources": self.min_sources,
            "max_sources": self.max_sources,
            "preferred_paper_types": list(self.preferred_paper_types),
            "preferred_research_designs": list(
                self.preferred_research_designs
            ),
            "max_age_years": self.max_age_years,
            "full_text_required": self.full_text_required,
            "min_relevance_score": self.min_relevance_score,
            "coverage_weight": self.coverage_weight,
            "retrieval_intents": list(self.retrieval_intents),
        }


@dataclass(frozen=True)
class SectionSnapshot:
    source_plan_section_id: str
    section_key: str
    title: str
    purpose: str | None
    section_type: str
    display_order: int
    required: bool
    word_budget: int
    budget_weight: float
    evidence_coverage_target: float
    requirements: list[RequirementSnapshot]

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_plan_section_id": self.source_plan_section_id,
            "section_key": self.section_key,
            "title": self.title,
            "purpose": self.purpose,
            "section_type": self.section_type,
            "display_order": self.display_order,
            "required": self.required,
            "word_budget": self.word_budget,
            "budget_weight": self.budget_weight,
            "evidence_coverage_target": self.evidence_coverage_target,
            "requirements": [r.as_dict() for r in self.requirements],
        }


def _snapshot_requirement(
    req: ResearchEvidenceRequirement,
) -> RequirementSnapshot:
    intents = list(map_requirement_type_to_intents(req.requirement_type))
    return RequirementSnapshot(
        requirement_id=str(req.id),
        requirement_key=req.requirement_key,
        requirement_type=req.requirement_type,
        required=bool(req.required),
        priority=int(req.priority),
        min_sources=req.min_sources,
        max_sources=req.max_sources,
        preferred_paper_types=list(req.preferred_paper_types or []),
        preferred_research_designs=list(
            req.preferred_research_designs or []
        ),
        max_age_years=req.max_age_years,
        full_text_required=bool(req.full_text_required),
        min_relevance_score=(
            float(req.min_relevance_score)
            if req.min_relevance_score is not None else None
        ),
        coverage_weight=float(req.coverage_weight),
        retrieval_intents=intents,
    )


def _resolve_coverage_target(
    reqs: list[RequirementSnapshot],
    section: ResearchPlanSection,
) -> float:
    m24 = float(section.evidence_coverage_target or 0.0)
    if 0.0 < m24 <= 1.0:
        return m24
    required = [r for r in reqs if r.required]
    if not required:
        return 0.0
    weights = [r.coverage_weight for r in required if r.coverage_weight > 0]
    if not weights:
        return 0.0
    avg = sum(weights) / len(weights)
    return max(0.0, min(1.0, round(avg, 4)))


def build_section_snapshots(
    *,
    plan: ResearchPlan,
    sections: list[ResearchPlanSection],
    requirements: list[ResearchEvidenceRequirement],
    word_budget_by_section: dict[str, int] | None = None,
) -> tuple[list[SectionSnapshot], list[str]]:
    reqs_by_section: dict[str, list[ResearchEvidenceRequirement]] = {}
    for r in requirements:
        reqs_by_section.setdefault(str(r.section_id), []).append(r)

    wb = word_budget_by_section or {}
    warnings: list[str] = []
    snapshots: list[SectionSnapshot] = []

    ordered = sorted(sections, key=lambda s: (s.display_order, s.section_key))
    for s in ordered:
        sid = str(s.id)
        reqs = sorted(
            reqs_by_section.get(sid, []),
            key=lambda r: (-int(r.priority), r.requirement_key),
        )
        snap_reqs: list[RequirementSnapshot] = []
        for r in reqs:
            snap = _snapshot_requirement(r)
            if snap.required and not snap.retrieval_intents:
                warnings.append(
                    f"unmapped_required_requirement:{snap.requirement_key}"
                )
            snap_reqs.append(snap)

        target = _resolve_coverage_target(snap_reqs, s)
        snapshots.append(SectionSnapshot(
            source_plan_section_id=sid,
            section_key=s.section_key,
            title=s.title,
            purpose=s.purpose,
            section_type=s.section_type,
            display_order=int(s.display_order),
            required=bool(s.required),
            word_budget=int(wb.get(s.section_key, s.word_budget)),
            budget_weight=float(s.budget_weight),
            evidence_coverage_target=target,
            requirements=snap_reqs,
        ))
    return snapshots, warnings


def aggregate_source_constraints(
    reqs: list[RequirementSnapshot],
) -> dict[str, Any]:
    required = [r for r in reqs if r.required]
    mins = [r.min_sources for r in required if r.min_sources is not None]
    maxs = [r.max_sources for r in required if r.max_sources is not None]
    ages = [r.max_age_years for r in required if r.max_age_years is not None]
    rels = [
        r.min_relevance_score for r in required
        if r.min_relevance_score is not None
    ]

    pref_pt: set[str] = set()
    pref_rd: set[str] = set()
    for r in reqs:
        pref_pt.update(r.preferred_paper_types)
        pref_rd.update(r.preferred_research_designs)

    return {
        "min_sources": max(mins) if mins else None,
        "max_sources": min(maxs) if maxs else None,
        "preferred_paper_types": sorted(pref_pt),
        "preferred_research_designs": sorted(pref_rd),
        "max_age_years": min(ages) if ages else None,
        "full_text_required": any(r.full_text_required for r in required),
        "min_relevance_score": max(rels) if rels else None,
    }


def build_research_contract(snap: SectionSnapshot) -> dict[str, Any]:
    intents: list[str] = []
    for r in snap.requirements:
        for i in r.retrieval_intents:
            if i not in intents:
                intents.append(i)
    required_reqs = [r for r in snap.requirements if r.required]
    citation = citation_required_for(
        snap.section_type, has_required_evidence=bool(required_reqs)
    )
    objective = _build_objective(snap)
    return {
        "section_key": snap.section_key,
        "research_objective": objective,
        "retrieval_intents": intents,
        "evidence_requirements": [r.as_dict() for r in snap.requirements],
        "source_constraints": aggregate_source_constraints(snap.requirements),
        "coverage_target": float(snap.evidence_coverage_target),
        "citation_required": citation,
        "intent_mapping_version": MANUSCRIPT_INTENT_MAPPING_VERSION,
    }


def _build_objective(snap: SectionSnapshot) -> str:
    base = (snap.purpose or "").strip()
    if not base:
        base = f"Address the {snap.section_type} section."
    return f"{snap.section_type}: {base}"


def extract_dependency_edges(
    *,
    sections: list[ResearchPlanSection],
    deps: list[ResearchPlanDependency],
) -> list[tuple[str, str, str]]:
    by_id = {str(s.id): s.section_key for s in sections}
    out: list[tuple[str, str, str]] = []
    for d in deps:
        up = by_id.get(str(d.upstream_section_id))
        down = by_id.get(str(d.downstream_section_id))
        if up and down:
            out.append((up, down, d.dependency_type or "requires"))
    out.sort()
    return out


__all__ = [
    "RequirementSnapshot",
    "SectionSnapshot",
    "build_section_snapshots",
    "build_research_contract",
    "aggregate_source_constraints",
    "extract_dependency_edges",
]
