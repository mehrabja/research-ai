"""M24 — Evidence requirement builder."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.db.models.literature import LiteratureCluster, LiteratureGap
from app.domain.research_plan import EvidenceRequirementType as ERT
from app.services.research_planning.templates import ResearchPlanTemplate


@dataclass(frozen=True)
class EvidenceRequirementDraft:
    section_key: str
    requirement_key: str
    requirement_type: str
    description: str
    required: bool
    priority: int
    min_sources: int | None
    max_sources: int | None
    preferred_paper_types: list[str] | None
    preferred_research_designs: list[str] | None
    max_age_years: int | None
    full_text_required: bool
    min_relevance_score: float | None
    coverage_weight: float
    meta: dict[str, Any]


_GAP_TO_EXTRA: dict[str, tuple[ERT, str, int]] = {
    "temporal_gap": (
        ERT.RECENT_EVIDENCE,
        "Recent evidence addressing temporal gap.",
        8,
    ),
    "population_gap": (
        ERT.PRIMARY_STUDY,
        "Evidence covering under-represented populations.",
        8,
    ),
    "contradiction_gap": (
        ERT.COUNTER_EVIDENCE,
        "Evidence resolving contradictory findings.",
        9,
    ),
    "evidence_gap": (
        ERT.PRIMARY_STUDY,
        "Primary evidence addressing the identified gap.",
        8,
    ),
    "methodology_gap": (
        ERT.METHODOLOGY,
        "Methodological evidence addressing the gap.",
        8,
    ),
    "comparative_gap": (
        ERT.COMPARATIVE,
        "Comparative evidence addressing the gap.",
        8,
    ),
    "outcome_gap": (
        ERT.PRIMARY_STUDY,
        "Evidence on under-studied outcomes.",
        7,
    ),
    "theoretical_gap": (
        ERT.THEORY,
        "Theoretical work addressing the gap.",
        7,
    ),
}


def build_evidence_requirements(
    *,
    template: ResearchPlanTemplate,
    paper_type_code: str | None,
    research_design_code: str | None,
    gaps: list[LiteratureGap],
    clusters: list[LiteratureCluster],
) -> list[EvidenceRequirementDraft]:
    drafts: list[EvidenceRequirementDraft] = []

    for section in template.sections:
        for er in section.evidence_requirements:
            preferred_types = list(er.get("preferred_paper_types") or [])
            if (
                not preferred_types
                and paper_type_code
                and er["type"] == ERT.PRIMARY_STUDY.value
            ):
                preferred_types = [paper_type_code]
            drafts.append(
                EvidenceRequirementDraft(
                    section_key=section.key,
                    requirement_key=er["key"],
                    requirement_type=er["type"],
                    description=er["description"],
                    required=bool(er.get("required", True)),
                    priority=int(er.get("priority", 5)),
                    min_sources=er.get("min_sources"),
                    max_sources=er.get("max_sources"),
                    preferred_paper_types=preferred_types or None,
                    preferred_research_designs=(
                        er.get("preferred_research_designs")
                        or (
                            [research_design_code]
                            if research_design_code
                            else None
                        )
                    ),
                    max_age_years=er.get("max_age_years"),
                    full_text_required=bool(
                        er.get("full_text_required", False)
                    ),
                    min_relevance_score=er.get("min_relevance_score"),
                    coverage_weight=float(
                        er.get("coverage_weight", 1.0)
                    ),
                    meta={},
                )
            )

    seen_types: set[str] = set()
    for gap in gaps:
        mapping = _GAP_TO_EXTRA.get(gap.gap_type)
        if mapping is None:
            continue
        req_type, desc, priority = mapping
        if req_type.value in seen_types:
            continue
        seen_types.add(req_type.value)
        drafts.append(
            EvidenceRequirementDraft(
                section_key="discussion",
                requirement_key=f"gap.{gap.gap_type}",
                requirement_type=req_type.value,
                description=desc,
                required=False,
                priority=priority,
                min_sources=1,
                max_sources=None,
                preferred_paper_types=None,
                preferred_research_designs=None,
                max_age_years=(
                    5 if gap.gap_type == "temporal_gap" else None
                ),
                full_text_required=False,
                min_relevance_score=None,
                coverage_weight=0.6,
                meta={"source_gap_id": str(gap.id)},
            )
        )

    if clusters:
        drafts.append(
            EvidenceRequirementDraft(
                section_key="related_work",
                requirement_key="cluster.synthesis",
                requirement_type=ERT.SYNTHESIS.value,
                description=(
                    "Synthesis evidence covering identified clusters "
                    "of prior work."
                ),
                required=False,
                priority=5,
                min_sources=max(1, len(clusters)),
                max_sources=None,
                preferred_paper_types=None,
                preferred_research_designs=None,
                max_age_years=None,
                full_text_required=False,
                min_relevance_score=None,
                coverage_weight=0.5,
                meta={"cluster_count": len(clusters)},
            )
        )

    dedup: dict[str, EvidenceRequirementDraft] = {}
    for d in drafts:
        dedup.setdefault(d.requirement_key, d)
    return list(dedup.values())
