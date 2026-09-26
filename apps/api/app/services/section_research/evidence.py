"""M28 — Deterministic evidence selection + per-requirement matching."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from app.db.models.literature import ProjectLiteratureItem
from app.db.models.source import Source
from app.domain.research_plan import RESEARCH_PLAN_REFERENCE_YEAR

_SCREENING_INCLUDED = frozenset({"candidate", "included"})
_FULL_TEXT_STATUSES = frozenset(
    {"extracted", "full_text", "structured_full_text"}
)
DEFAULT_PER_SOURCE_CAP = 3


@dataclass(frozen=True)
class EvidenceItem:
    source_id: uuid.UUID
    chunk_id: uuid.UUID | None
    rank: int
    final_score: float
    retrieval_stage: str
    retrieval_reason: list[str]
    matched_requirement_keys: tuple[str, ...]
    excerpt: str | None
    citation_label: str | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_id": str(self.source_id),
            "chunk_id": str(self.chunk_id) if self.chunk_id else None,
            "rank": int(self.rank),
            "final_score": float(self.final_score),
            "retrieval_stage": self.retrieval_stage,
            "retrieval_reason": list(self.retrieval_reason),
            "matched_requirement_keys": list(
                self.matched_requirement_keys
            ),
            "excerpt": self.excerpt,
            "citation_label": self.citation_label,
        }


@dataclass
class RequirementMatch:
    requirement_key: str
    matched_source_ids: set[uuid.UUID] = field(default_factory=set)
    matched_chunk_ids: set[uuid.UUID] = field(default_factory=set)

    @property
    def distinct_sources(self) -> int:
        return len(self.matched_source_ids)

    @property
    def matching_chunks(self) -> int:
        return len(self.matched_chunk_ids)


@dataclass
class EvidenceSelection:
    selected: list[EvidenceItem]
    matches: dict[str, RequirementMatch]
    warnings: list[str] = field(default_factory=list)


def _is_full_text(source: Source | None) -> bool:
    if source is None:
        return False
    if source.extracted_at is not None:
        return True
    return (source.status or "").lower() in _FULL_TEXT_STATUSES


def _citation_label(source: Source) -> str:
    authors = source.authors or []
    first = authors[0] if authors else None
    if isinstance(first, dict):
        first = first.get("name") or first.get("family") or None
    if first:
        first_str = str(first).strip()
    else:
        first_str = (source.title or "").strip().split(" ")[0] if source.title else ""
    year = source.year if source.year is not None else "n.d."
    if first_str:
        return f"{first_str} et al., {year}"
    if source.title:
        return f"{source.title} ({year})"
    return f"source:{source.id} ({year})"


def matches_requirement(
    *,
    source: Source | None,
    literature: ProjectLiteratureItem | None,
    requirement: dict[str, Any],
    reference_year: int = RESEARCH_PLAN_REFERENCE_YEAR,
) -> bool:
    if source is None:
        return False

    if (
        literature is not None
        and literature.screening_status not in _SCREENING_INCLUDED
    ):
        return False

    pref_pt = requirement.get("preferred_paper_types") or []
    if pref_pt:
        if literature is None:
            return False
        code = literature.paper_type_code
        if code is None or code not in {str(x) for x in pref_pt}:
            return False

    pref_rd = requirement.get("preferred_research_designs") or []
    if pref_rd:
        if literature is None:
            return False
        code = literature.research_design_code
        if code is None or code not in {str(x) for x in pref_rd}:
            return False

    min_rel = requirement.get("min_relevance_score")
    if min_rel is not None:
        if literature is None or literature.relevance_score is None:
            return False
        if float(literature.relevance_score) < float(min_rel):
            return False

    max_age = requirement.get("max_age_years")
    if max_age is not None:
        if source.year is None:
            return False
        if (reference_year - source.year) > int(max_age):
            return False

    if bool(requirement.get("full_text_required", False)):
        return _is_full_text(source)

    return True


def _excerpt_for(
    candidate: dict, *, chunk_contents: dict[uuid.UUID, str],
    excerpt_chars: int,
) -> str | None:
    cid = candidate.get("chunk_id")
    if cid is None:
        return None
    content = chunk_contents.get(cid)
    if not content:
        return None
    if len(content) <= excerpt_chars:
        return content
    return content[:excerpt_chars].rstrip()


def select_evidence(
    *,
    candidates: list[dict],
    requirements: tuple[dict[str, Any], ...],
    sources_by_id: dict[uuid.UUID, Source],
    literature_by_source_id: dict[uuid.UUID, ProjectLiteratureItem],
    chunk_contents: dict[uuid.UUID, str],
    excerpt_chars: int = 400,
    max_evidence: int = 30,
    per_source_cap: int = DEFAULT_PER_SOURCE_CAP,
    reference_year: int = RESEARCH_PLAN_REFERENCE_YEAR,
) -> EvidenceSelection:
    warnings: list[str] = []

    matches: dict[str, RequirementMatch] = {
        r["requirement_key"]: RequirementMatch(
            requirement_key=r["requirement_key"]
        )
        for r in requirements
    }

    # Pass 1: compute matches per requirement over ALL candidates
    for c in candidates:
        src_id = c.get("source_id")
        if src_id is None:
            continue
        source = sources_by_id.get(src_id)
        if source is None:
            continue
        literature = literature_by_source_id.get(src_id)
        for req in requirements:
            rk = req["requirement_key"]
            if matches_requirement(
                source=source,
                literature=literature,
                requirement=req,
                reference_year=reference_year,
            ):
                m = matches[rk]
                m.matched_source_ids.add(src_id)
                cid = c.get("chunk_id")
                if cid is not None:
                    m.matched_chunk_ids.add(cid)

    # Pass 2: select evidence (deterministic, capped, per-source cap)
    selected: list[EvidenceItem] = []
    per_source_count: dict[uuid.UUID, int] = {}
    has_requirements = bool(requirements)

    for c in candidates:
        if len(selected) >= max_evidence:
            break
        src_id = c.get("source_id")
        if src_id is None:
            continue
        source = sources_by_id.get(src_id)
        if source is None:
            continue

        # Which requirements does this candidate satisfy?
        literature = literature_by_source_id.get(src_id)
        matched_keys: list[str] = []
        for req in requirements:
            if matches_requirement(
                source=source,
                literature=literature,
                requirement=req,
                reference_year=reference_year,
            ):
                matched_keys.append(req["requirement_key"])

        if has_requirements and not matched_keys:
            continue

        # Per-source cap
        if per_source_count.get(src_id, 0) >= per_source_cap:
            continue

        cid = c.get("chunk_id")
        selected.append(EvidenceItem(
            source_id=src_id,
            chunk_id=cid,
            rank=int(c.get("rank", 0)),
            final_score=float(c.get("final_score", 0.0)),
            retrieval_stage=str(c.get("retrieval_stage") or "hybrid"),
            retrieval_reason=list(c.get("retrieval_reason") or []),
            matched_requirement_keys=tuple(matched_keys),
            excerpt=_excerpt_for(
                c, chunk_contents=chunk_contents,
                excerpt_chars=excerpt_chars,
            ),
            citation_label=_citation_label(source),
        ))
        per_source_count[src_id] = per_source_count.get(src_id, 0) + 1

    # Diagnostics
    for req in requirements:
        rk = req["requirement_key"]
        m = matches[rk]
        if bool(req.get("required", False)) and m.distinct_sources == 0:
            warnings.append(f"requirement_unsatisfied:{rk}")

    if has_requirements and not selected:
        warnings.append("no_evidence_matched_any_requirement")

    return EvidenceSelection(
        selected=selected, matches=matches, warnings=warnings,
    )


__all__ = [
    "DEFAULT_PER_SOURCE_CAP",
    "EvidenceItem",
    "RequirementMatch",
    "EvidenceSelection",
    "matches_requirement",
    "select_evidence",
]
