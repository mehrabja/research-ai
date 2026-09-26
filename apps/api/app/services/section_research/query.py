"""M28 — Deterministic query construction from a section contract."""
from __future__ import annotations

from dataclasses import dataclass

from app.core.exceptions import SectionResearchContractInvalid
from app.domain.section_research import (
    INTENT_QUERY_KEYWORD,
    SECTION_RESEARCH_QUERY_VERSION,
)


@dataclass(frozen=True)
class QueryPlan:
    primary: str
    derived: tuple[str, ...]
    version: str = SECTION_RESEARCH_QUERY_VERSION

    def all_queries(self) -> tuple[str, ...]:
        return (self.primary,) + self.derived

    def as_dict(self) -> dict:
        return {
            "version": self.version,
            "primary": self.primary,
            "derived": list(self.derived),
        }


def _normalize(text: str) -> str:
    return " ".join(text.split()).strip()


def build_query_plan(
    *,
    research_objective: str,
    retrieval_intents: list[str],
    max_queries: int = 5,
) -> QueryPlan:
    primary = _normalize(research_objective or "")
    if not primary:
        raise SectionResearchContractInvalid(
            "empty research objective; cannot build queries"
        )

    cap = max(1, int(max_queries))
    if cap == 1:
        return QueryPlan(primary=primary, derived=())

    seen: set[str] = set()
    ordered: list[str] = []
    for i in retrieval_intents:
        if i in seen:
            continue
        seen.add(i)
        ordered.append(i)

    derived: list[str] = []
    for intent in ordered:
        kw = INTENT_QUERY_KEYWORD.get(intent)
        if kw is None:
            continue
        derived.append(f"{kw}: {primary}")
        if len(derived) >= cap - 1:
            break

    return QueryPlan(primary=primary, derived=tuple(derived))


__all__ = ["QueryPlan", "build_query_plan"]
