"""M28 — Translate source_constraints into M26-compatible filters."""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from app.domain.research_plan import RESEARCH_PLAN_REFERENCE_YEAR


@dataclass(frozen=True)
class EffectiveFilters:
    min_year: int | None
    max_year: int | None
    required_full_text: bool
    allowed_source_ids: tuple[uuid.UUID, ...]
    # Domain-specific constraints that M26 does not understand.
    # Kept here for post-filtering by M28.
    preferred_paper_types: tuple[str, ...]
    preferred_research_designs: tuple[str, ...]
    min_relevance_score: float | None

    def m26_dict(self) -> dict[str, Any]:
        return {
            "min_year": self.min_year,
            "max_year": self.max_year,
            "required_full_text": self.required_full_text,
            "allowed_source_ids": [
                str(x) for x in self.allowed_source_ids
            ],
        }

    def as_dict(self) -> dict[str, Any]:
        return {
            "min_year": self.min_year,
            "max_year": self.max_year,
            "required_full_text": self.required_full_text,
            "allowed_source_ids": sorted(
                str(x) for x in self.allowed_source_ids
            ),
            "preferred_paper_types": list(self.preferred_paper_types),
            "preferred_research_designs": list(
                self.preferred_research_designs
            ),
            "min_relevance_score": self.min_relevance_score,
        }


def build_effective_filters(
    *,
    source_constraints: dict[str, Any],
    reference_year: int = RESEARCH_PLAN_REFERENCE_YEAR,
) -> tuple[EffectiveFilters, list[str]]:
    warnings: list[str] = []

    max_age = source_constraints.get("max_age_years")
    min_year: int | None = None
    max_year: int | None = None
    if isinstance(max_age, int) and max_age > 0:
        min_year = reference_year - max_age
        max_year = reference_year

    full_text = bool(
        source_constraints.get("full_text_required") or False
    )

    pref_pt_raw = source_constraints.get("preferred_paper_types") or []
    pref_rd_raw = (
        source_constraints.get("preferred_research_designs") or []
    )
    pref_pt = tuple(str(x) for x in pref_pt_raw if x)
    pref_rd = tuple(str(x) for x in pref_rd_raw if x)

    min_rel = source_constraints.get("min_relevance_score")
    if min_rel is not None:
        try:
            min_rel = float(min_rel)
        except (TypeError, ValueError):
            warnings.append("invalid_min_relevance_score")
            min_rel = None

    return (
        EffectiveFilters(
            min_year=min_year,
            max_year=max_year,
            required_full_text=full_text,
            allowed_source_ids=(),
            preferred_paper_types=pref_pt,
            preferred_research_designs=pref_rd,
            min_relevance_score=min_rel,
        ),
        warnings,
    )


__all__ = ["EffectiveFilters", "build_effective_filters"]
