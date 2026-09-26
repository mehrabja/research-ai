"""M23 — Deterministic, explainable literature screening.

Relevance compares the Source against the ProjectClassification:
  * domain_match: overlap between source text and the taxonomy
    domain's code/name/aliases for the classification's domain_id.
  * paper_type_match: taxonomy heuristic extraction vs
    classification's paper_type_code.
  * research_design_match: same for research_design_code.
  * question_overlap: project.research_questions keywords vs source.
  * text_availability, citation_signal, recency, metadata_quality.

Every factor has a fixed name, weight, and value in [0, 1].
"""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.literature import ProjectLiteratureItem
from app.db.models.project import Project
from app.db.models.research_classification import ProjectClassification
from app.db.models.research_taxonomy import (
    ResearchDomain as ResearchDomainRow,
)
from app.db.models.source import Source
from app.domain.literature import SCREENING_VERSION
from app.services.literature.characterization import (
    _extract_design,
    _extract_paper_type,
)

_CANDIDATE_THRESHOLD = 0.5


@dataclass(frozen=True)
class ScreeningFactor:
    name: str
    weight: float
    value: float


@dataclass(frozen=True)
class ScreeningResult:
    screening_status: str
    relevance_score: float
    confidence: float
    reason: str
    factors: list[dict]
    version: str


def _norm(t: str | None) -> str:
    return (t or "").lower()


def _source_text(source: Source) -> str:
    parts: list[str] = [source.title or ""]
    if source.abstract:
        parts.append(source.abstract)
    return " ".join(parts)


def _domain_match(
    db: Session,
    source: Source,
    cls: ProjectClassification | None,
) -> ScreeningFactor:
    if cls is None or cls.domain_id is None:
        return ScreeningFactor("domain_match", 0.30, 0.3)
    dom = db.get(ResearchDomainRow, cls.domain_id)
    if dom is None:
        return ScreeningFactor("domain_match", 0.30, 0.3)
    needles: set[str] = set()
    if dom.code:
        needles.add(dom.code.lower())
    if dom.name:
        needles.add(dom.name.lower())
    for a in (dom.aliases or []):
        if isinstance(a, str) and a:
            needles.add(a.lower())
    needles.discard("")
    if not needles:
        return ScreeningFactor("domain_match", 0.30, 0.3)
    hay = _norm(_source_text(source))
    hits = sum(1 for n in needles if n in hay)
    value = min(1.0, hits / len(needles))
    return ScreeningFactor("domain_match", 0.30, value)


def _paper_type_match(
    source: Source,
    cls: ProjectClassification | None,
) -> ScreeningFactor:
    if cls is None or not cls.paper_type_code:
        return ScreeningFactor("paper_type_match", 0.10, 0.3)
    detected = _extract_paper_type(_source_text(source)) or ""
    value = (
        1.0
        if detected and detected == cls.paper_type_code
        else 0.0
    )
    return ScreeningFactor("paper_type_match", 0.10, value)


def _design_match(
    source: Source,
    cls: ProjectClassification | None,
) -> ScreeningFactor:
    if cls is None or not cls.research_design_code:
        return ScreeningFactor("research_design_match", 0.10, 0.3)
    detected = _extract_design(_source_text(source)) or ""
    value = (
        1.0
        if detected and detected == cls.research_design_code
        else 0.0
    )
    return ScreeningFactor("research_design_match", 0.10, value)


def _question_overlap(
    db: Session,
    source: Source,
    project_id: uuid.UUID,
) -> ScreeningFactor:
    proj = db.get(Project, project_id)
    if proj is None:
        return ScreeningFactor("question_overlap", 0.15, 0.0)
    questions = proj.research_questions or []
    tokens: set[str] = set()
    for q in questions:
        if isinstance(q, str):
            for w in re.findall(r"[a-zA-Z]{4,}", q.lower()):
                tokens.add(w)
    if not tokens:
        return ScreeningFactor("question_overlap", 0.15, 0.0)
    hay = _norm(_source_text(source))
    hits = sum(1 for t in tokens if t in hay)
    value = min(1.0, hits / len(tokens))
    return ScreeningFactor("question_overlap", 0.15, value)


def _text_availability(source: Source) -> ScreeningFactor:
    has_abs = bool(source.abstract and source.abstract.strip())
    has_full = bool(source.full_text and source.full_text.strip())
    if has_full:
        return ScreeningFactor("text_availability", 0.15, 1.0)
    if has_abs:
        return ScreeningFactor("text_availability", 0.15, 0.6)
    return ScreeningFactor("text_availability", 0.15, 0.0)


def _citation_signal(source: Source) -> ScreeningFactor:
    c = source.citation_count or 0
    if c >= 50:
        v = 1.0
    elif c >= 10:
        v = 0.7
    elif c >= 1:
        v = 0.3
    else:
        v = 0.0
    return ScreeningFactor("citation_signal", 0.05, v)


def _recency(source: Source) -> ScreeningFactor:
    y = source.year or 0
    if y >= 2020:
        v = 1.0
    elif y >= 2015:
        v = 0.7
    elif y >= 2010:
        v = 0.4
    elif y > 0:
        v = 0.2
    else:
        v = 0.0
    return ScreeningFactor("recency", 0.05, v)


def _metadata_quality(source: Source) -> ScreeningFactor:
    have = 0
    total = 4
    if source.doi:
        have += 1
    if source.year:
        have += 1
    if source.authors:
        have += 1
    if source.url:
        have += 1
    return ScreeningFactor("metadata_quality", 0.05, have / total)


def _weighted_score(factors: list[ScreeningFactor]) -> float:
    total_w = sum(f.weight for f in factors)
    if total_w <= 0:
        return 0.0
    return sum(f.weight * f.value for f in factors) / total_w


def _confidence(factors: list[ScreeningFactor]) -> float:
    strong = sum(1 for f in factors if f.value >= 0.5)
    return min(1.0, 0.4 + 0.1 * strong)


def screen_literature_item(
    db: Session,
    *,
    item: ProjectLiteratureItem,
    source: Source,
    classification: ProjectClassification | None = None,
) -> ScreeningResult:
    if classification is None:
        classification = db.execute(
            select(ProjectClassification).where(
                ProjectClassification.project_id == item.project_id
            )
        ).scalar_one_or_none()

    factors = [
        _domain_match(db, source, classification),
        _paper_type_match(source, classification),
        _design_match(source, classification),
        _question_overlap(db, source, item.project_id),
        _text_availability(source),
        _citation_signal(source),
        _recency(source),
        _metadata_quality(source),
    ]
    score = _weighted_score(factors)
    status = (
        "candidate" if score >= _CANDIDATE_THRESHOLD else "discovered"
    )
    top = max(factors, key=lambda f: f.weight * f.value)
    reason = (
        f"weighted score {score:.2f}; dominant factor "
        f"'{top.name}' = {top.value:.2f}"
    )
    return ScreeningResult(
        screening_status=status,
        relevance_score=round(score, 4),
        confidence=round(_confidence(factors), 4),
        reason=reason,
        factors=[
            {"name": f.name, "weight": f.weight, "value": f.value}
            for f in factors
        ],
        version=SCREENING_VERSION,
    )


def apply_screening(
    db: Session,
    *,
    item: ProjectLiteratureItem,
    source: Source,
    classification: ProjectClassification | None = None,
) -> ScreeningResult:
    """Compute + persist. Manual overrides are never clobbered.

    Does NOT commit — caller owns transaction.
    """
    result = screen_literature_item(
        db, item=item, source=source, classification=classification
    )
    if item.manual_override:
        return result
    item.screening_status = result.screening_status
    item.relevance_score = Decimal(str(result.relevance_score))
    item.relevance_confidence = Decimal(str(result.confidence))
    item.relevance_reason = result.reason
    item.relevance_factors = result.factors
    db.flush()
    return result


__all__ = [
    "ScreeningFactor",
    "ScreeningResult",
    "apply_screening",
    "screen_literature_item",
]
