"""M21 — Domain classifier (heuristic-first, DB taxonomy-backed)."""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.classification.context import (
    ClassificationContext,
)
from app.services.classification.evidence import (
    EvidenceCollector,
    EvidenceItem,
)
from app.services.classification.taxonomy import list_active_domains
from app.services.classification.text_match import contains_alias

_LOCATION_WEIGHTS: dict[str, float] = {
    "project.description": 0.35,
    "project.research_objective": 0.5,
    "project.research_questions": 0.45,
    "project.hypotheses": 0.4,
    "project.scope": 0.35,
    "project.constraints": 0.3,
    "report:": 0.4,
    "report_version:": 0.3,
    "file:": 0.2,
}


def _weight_for(location: str) -> float:
    for prefix in (
        "project.description", "project.research_objective",
        "project.research_questions", "project.hypotheses",
        "project.scope", "project.constraints",
        "report_version:", "report:", "file:",
    ):
        if location.startswith(prefix):
            return _LOCATION_WEIGHTS[prefix]
    return 0.1


@dataclass
class DomainCandidate:
    code: str
    name: str
    confidence: float = 0.0
    evidence: list[EvidenceItem] = field(default_factory=list)


@dataclass
class DomainResult:
    primary_code: str | None
    primary_confidence: float | None
    source: str
    method: str
    reason: str | None
    alternatives: list[dict]
    evidence: list[EvidenceItem]


def _noisy_or(weights: list[float]) -> float:
    p = 1.0
    for w in weights:
        p *= (1.0 - w)
    return 1.0 - p


def classify_domain(
    db: Session,
    *,
    ctx: ClassificationContext,
    collector: EvidenceCollector,
) -> DomainResult:
    settings = get_settings()
    domains = list_active_domains(db)
    if not domains:
        return DomainResult(
            primary_code=None,
            primary_confidence=None,
            source="inferred",
            method="heuristic",
            reason="empty taxonomy",
            alternatives=[],
            evidence=[],
        )

    explicit = (ctx.explicit_domain or "").strip()
    if explicit:
        low = explicit.lower()
        for d in domains:
            if low == d.code.lower() or low == d.name.lower():
                collector.add(
                    EvidenceItem(
                        target="domain",
                        signal_type="explicit_field",
                        source_location="project.domain",
                        matched_text=explicit,
                        weight=1.0,
                        target_code=d.code,
                    )
                )
                return DomainResult(
                    primary_code=d.code,
                    primary_confidence=1.0,
                    source="explicit",
                    method="explicit",
                    reason=(
                        "Project.domain exactly matches taxonomy code/name"
                    ),
                    alternatives=[],
                    evidence=collector.items_for("domain"),
                )
            if low in [a.lower() for a in (d.aliases or [])]:
                collector.add(
                    EvidenceItem(
                        target="domain",
                        signal_type="explicit_field",
                        source_location="project.domain",
                        matched_text=explicit,
                        weight=0.9,
                        target_code=d.code,
                    )
                )
                return DomainResult(
                    primary_code=d.code,
                    primary_confidence=0.9,
                    source="explicit",
                    method="explicit",
                    reason="Project.domain matches a taxonomy alias",
                    alternatives=[],
                    evidence=collector.items_for("domain"),
                )

    candidates: dict[str, DomainCandidate] = {
        d.code: DomainCandidate(code=d.code, name=d.name) for d in domains
    }

    for chunk in ctx.chunks:
        if not chunk.text:
            continue
        weight = _weight_for(chunk.location)
        for d in domains:
            needles = [d.code, d.name] + list(d.aliases or [])
            for needle in needles:
                if not needle:
                    continue
                if contains_alias(chunk.text, str(needle)):
                    ev = EvidenceItem(
                        target="domain",
                        signal_type="alias_match",
                        source_location=chunk.location,
                        matched_text=str(needle),
                        weight=weight,
                        target_code=d.code,
                    )
                    collector.add(ev)
                    candidates[d.code].evidence.append(ev)

    ranked: list[DomainCandidate] = []
    for c in candidates.values():
        weights = [e.weight for e in c.evidence]
        if not weights:
            continue
        c.confidence = _noisy_or(weights)
        ranked.append(c)

    ranked.sort(key=lambda c: c.confidence, reverse=True)
    ranked = ranked[: settings.classification_max_alternatives + 1]

    if not ranked:
        return DomainResult(
            primary_code=None,
            primary_confidence=None,
            source="inferred",
            method="heuristic",
            reason="no signal matched any taxonomy entry",
            alternatives=[],
            evidence=collector.items_for("domain"),
        )

    top = ranked[0]
    alt = [
        {
            "code": c.code,
            "name": c.name,
            "confidence": round(c.confidence, 4),
        }
        for c in ranked[1 : settings.classification_max_alternatives + 1]
    ]
    return DomainResult(
        primary_code=top.code,
        primary_confidence=round(top.confidence, 4),
        source="inferred",
        method="heuristic",
        reason=f"matched {len(top.evidence)} signal(s) across context",
        alternatives=alt,
        evidence=collector.items_for("domain"),
    )
