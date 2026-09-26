"""M28.5 — Per-section generation contracts from M27/M24.

We do NOT hardcode section rules; we read them from the section's
`research_contract` field (populated by M27).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.db.models.manuscript import ManuscriptSection


@dataclass
class SectionContract:
    section_key: str
    section_type: str
    display_order: int
    title: str
    purpose: str | None
    research_objective: str | None
    retrieval_intents: list[str] = field(default_factory=list)
    requirement_keys: list[str] = field(default_factory=list)
    citation_required: bool = False
    coverage_target: float = 0.0
    word_budget: int = 0
    extra: dict[str, Any] = field(default_factory=dict)


def build_section_contract(
    section: ManuscriptSection,
) -> SectionContract:
    rc = section.research_contract or {}
    requirements = rc.get("evidence_requirements") or []
    req_keys = [
        str(r.get("requirement_key"))
        for r in requirements
        if isinstance(r, dict) and r.get("requirement_key")
    ]
    return SectionContract(
        section_key=section.section_key,
        section_type=section.section_type,
        display_order=section.display_order,
        title=section.title,
        purpose=section.purpose,
        research_objective=rc.get("research_objective")
        or section.research_objective,
        retrieval_intents=list(rc.get("retrieval_intents") or []),
        requirement_keys=req_keys,
        citation_required=bool(section.citation_required),
        coverage_target=float(section.evidence_coverage_target or 0.0),
        word_budget=int(section.word_budget or 0),
        extra={
            "intent_mapping_version": rc.get("intent_mapping_version"),
        },
    )


__all__ = ["SectionContract", "build_section_contract"]
