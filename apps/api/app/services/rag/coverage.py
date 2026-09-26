"""M26 — Real intent-to-evidence coverage.

Deterministic. No LLM. No wall-clock time. Reference year comes from
``RESEARCH_PLAN_REFERENCE_YEAR`` (2026).

Evidence rules:
    * Only source-backed results count. Results whose ``source_id``
      is missing from ``sources_by_id`` are excluded.
    * ``causal_evidence`` requires BOTH an intervention/comparator
      signal AND a research design compatible with causal inference.
    * ``counter_evidence`` requires an explicit contradictory signal;
      ``limitations_summary`` alone is not counter evidence. M23 does
      not currently expose a contradiction field, so this matcher
      returns False and the intent remains ``missing`` with an
      explicit reason.
    * ``gap`` requires M25 graph context with source-backed gap
      references; a generic source-backed result is NOT enough.
    * ``synthesis`` and ``comparison`` require >= 2 distinct sources
      (multiple chunks of the same source do not count).
    * Graph-only nodes without a source id never count as evidence.
"""
from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass

from app.db.models.literature import ProjectLiteratureItem
from app.db.models.source import Source
from app.domain.research_plan import RESEARCH_PLAN_REFERENCE_YEAR

INTENT_COVERAGE_VERSION = "m26-coverage-v1"
INTENT_COVERAGE_SATISFIED_THRESHOLD = 0.70
INTENT_COVERAGE_WEAK_THRESHOLD = 0.40

_RECENT_WINDOW_YEARS = 5
_SCREENING_INCLUDED = frozenset({"candidate", "included"})

_CAUSAL_DESIGN_KEYWORDS: tuple[str, ...] = (
    "experimental",
    "randomi",
    "rct",
    "controlled_trial",
    "intervention",
    "quasi_experimental",
    "quasi-experimental",
)


@dataclass(frozen=True)
class IntentCoverage:
    intent: str
    score: float
    matching_results: int
    distinct_sources: int
    state: str
    reasons: list[str]


_Matcher = Callable[
    [dict, "Source | None", "ProjectLiteratureItem | None"], bool
]


@dataclass(frozen=True)
class _IntentRule:
    min_matching: int
    min_distinct_sources: int
    matcher: _Matcher


def _is_causal_design(design_code: str | None) -> bool:
    if not design_code:
        return False
    code = design_code.lower()
    return any(kw in code for kw in _CAUSAL_DESIGN_KEYWORDS)


def _clamp(v: float) -> float:
    return max(0.0, min(1.0, v))


def _result_relevance(
    r: dict, lit: ProjectLiteratureItem | None
) -> float:
    r_score = float(r.get("final_score", 0.0) or 0.0)
    if lit is None or lit.relevance_score is None:
        return _clamp(r_score)
    return _clamp(0.6 * r_score + 0.4 * float(lit.relevance_score))


def _matches_all(
    r: dict,
    s: Source | None,
    lit: ProjectLiteratureItem | None,
) -> bool:
    return True


def _matches_recent(
    r: dict,
    s: Source | None,
    lit: ProjectLiteratureItem | None,
) -> bool:
    if s is None or s.year is None:
        return False
    return (RESEARCH_PLAN_REFERENCE_YEAR - s.year) <= _RECENT_WINDOW_YEARS


def _matches_methodology(
    r: dict,
    s: Source | None,
    lit: ProjectLiteratureItem | None,
) -> bool:
    if lit is None:
        return False
    return (
        lit.methods_summary is not None
        or lit.research_design_code is not None
    )


def _matches_empirical(
    r: dict,
    s: Source | None,
    lit: ProjectLiteratureItem | None,
) -> bool:
    if lit is None:
        return False
    return (
        lit.study_summary is not None
        or lit.findings_summary is not None
    )


def _matches_causal(
    r: dict,
    s: Source | None,
    lit: ProjectLiteratureItem | None,
) -> bool:
    if lit is None:
        return False
    has_signal = (
        lit.intervention is not None or lit.comparator is not None
    )
    if not has_signal:
        return False
    return _is_causal_design(lit.research_design_code)


def _matches_limitation(
    r: dict,
    s: Source | None,
    lit: ProjectLiteratureItem | None,
) -> bool:
    if lit is None:
        return False
    return lit.limitations_summary is not None


def _matches_counter(
    r: dict,
    s: Source | None,
    lit: ProjectLiteratureItem | None,
) -> bool:
    """M23 has no explicit contradiction field — return False."""
    return False


def _matches_citation(
    r: dict,
    s: Source | None,
    lit: ProjectLiteratureItem | None,
) -> bool:
    return (
        r.get("source_id") is not None
        and r.get("chunk_id") is not None
    )


_INTENT_RULES: dict[str, _IntentRule] = {
    "background": _IntentRule(2, 2, _matches_all),
    "definition": _IntentRule(1, 1, _matches_all),
    "methodology": _IntentRule(1, 1, _matches_methodology),
    "empirical_evidence": _IntentRule(1, 1, _matches_empirical),
    "comparison": _IntentRule(2, 2, _matches_all),
    "causal_evidence": _IntentRule(1, 1, _matches_causal),
    "recent_evidence": _IntentRule(1, 1, _matches_recent),
    "counter_evidence": _IntentRule(1, 1, _matches_counter),
    "limitation": _IntentRule(1, 1, _matches_limitation),
    "gap": _IntentRule(1, 1, _matches_all),
    "synthesis": _IntentRule(2, 2, _matches_all),
    "citation": _IntentRule(1, 1, _matches_citation),
}


def _is_gap_eligible(
    source_id: uuid.UUID | None,
    *,
    gap_source_ids: set[uuid.UUID],
) -> bool:
    if source_id is None:
        return False
    return source_id in gap_source_ids


def _extract_gap_source_ids(
    graph_context: dict | None,
) -> set[uuid.UUID]:
    if not graph_context:
        return set()
    raw = graph_context.get("gap_source_ids")
    if not isinstance(raw, list):
        return set()
    out: set[uuid.UUID] = set()
    for item in raw:
        try:
            out.add(uuid.UUID(str(item)))
        except (ValueError, TypeError):
            continue
    return out


def compute_intent_coverage(
    *,
    intents: list[str],
    results: list[dict],
    sources_by_id: dict[uuid.UUID, Source],
    literature_by_source_id: dict[uuid.UUID, ProjectLiteratureItem],
    graph_context: dict | None = None,
) -> dict:
    """Compute deterministic intent-to-evidence coverage."""
    source_backed = [
        r
        for r in results
        if r.get("source_id") is not None
        and r.get("source_id") in sources_by_id
    ]

    gap_source_ids = _extract_gap_source_ids(graph_context)

    intent_scores: dict[str, float] = {}
    intent_details: dict[str, dict] = {}
    satisfied: list[str] = []
    weak: list[str] = []
    missing: list[str] = []

    for intent in intents:
        rule = _INTENT_RULES.get(intent)
        if rule is None:
            intent_scores[intent] = 0.0
            intent_details[intent] = {
                "matching_results": 0,
                "distinct_sources": 0,
                "score": 0.0,
                "state": "missing",
                "reasons": [f"unknown_intent:{intent}"],
            }
            missing.append(intent)
            continue

        matching: list[dict] = []
        for r in source_backed:
            if intent == "gap" and not _is_gap_eligible(
                r.get("source_id"),
                gap_source_ids=gap_source_ids,
            ):
                continue
            src = sources_by_id.get(r["source_id"])
            lit = literature_by_source_id.get(r["source_id"])
            if rule.matcher(r, src, lit):
                matching.append(r)

        matching_count = len(matching)
        distinct = len({r["source_id"] for r in matching})

        top_k = min(5, matching_count)
        if top_k == 0:
            relevance = 0.0
        else:
            ordered = sorted(
                matching,
                key=lambda r: (
                    -float(r.get("final_score", 0.0) or 0.0),
                    str(r.get("chunk_id") or r.get("source_id")),
                ),
            )
            top = ordered[:top_k]
            relevance = sum(
                _result_relevance(
                    r,
                    literature_by_source_id.get(r["source_id"]),
                )
                for r in top
            ) / len(top)

        count_score = _clamp(
            matching_count / max(1, rule.min_matching)
        )
        source_score = _clamp(
            distinct / max(1, rule.min_distinct_sources)
        )
        score = _clamp(
            0.35 * count_score
            + 0.35 * source_score
            + 0.30 * relevance
        )

        meets_min_matching = matching_count >= rule.min_matching
        meets_min_distinct = distinct >= rule.min_distinct_sources

        if not meets_min_matching or not meets_min_distinct:
            if matching_count == 0:
                state = "missing"
            elif score >= INTENT_COVERAGE_WEAK_THRESHOLD:
                state = "weak"
            else:
                state = "missing"
        elif score >= INTENT_COVERAGE_SATISFIED_THRESHOLD:
            state = "satisfied"
        elif score >= INTENT_COVERAGE_WEAK_THRESHOLD:
            state = "weak"
        else:
            state = "missing"

        reasons: list[str] = []
        if intent == "counter_evidence":
            reasons.append("no_counter_signal_in_m23_model")
        if intent == "gap" and not gap_source_ids:
            reasons.append("no_gap_context_available")
        if intent == "gap" and gap_source_ids:
            reasons.append(f"gap_sources={len(gap_source_ids)}")
        reasons.append(f"matched_results={matching_count}")
        reasons.append(f"matched_sources={distinct}")

        if state == "satisfied":
            if meets_min_matching:
                reasons.append("count_ok")
            if meets_min_distinct:
                reasons.append("sources_ok")
        else:
            if not meets_min_matching:
                reasons.append("insufficient_matching_results")
            if not meets_min_distinct:
                reasons.append("insufficient_distinct_sources")
            if top_k > 0 and relevance < INTENT_COVERAGE_WEAK_THRESHOLD:
                reasons.append("low_relevance")

        if state == "satisfied":
            satisfied.append(intent)
        elif state == "weak":
            weak.append(intent)
        else:
            missing.append(intent)

        intent_scores[intent] = round(score, 4)
        intent_details[intent] = {
            "matching_results": matching_count,
            "distinct_sources": distinct,
            "score": round(score, 4),
            "state": state,
            "reasons": reasons,
        }

    requested = list(intents)
    overall = (
        sum(intent_scores[i] for i in requested) / len(requested)
        if requested else 0.0
    )

    return {
        "coverage_version": INTENT_COVERAGE_VERSION,
        "overall_score": round(overall, 4),
        "requested_intents": requested,
        "satisfied_intents": satisfied,
        "weak_intents": weak,
        "missing_intents": missing,
        "intent_scores": intent_scores,
        "intent_details": intent_details,
    }


__all__ = [
    "INTENT_COVERAGE_VERSION",
    "INTENT_COVERAGE_SATISFIED_THRESHOLD",
    "INTENT_COVERAGE_WEAK_THRESHOLD",
    "IntentCoverage",
    "compute_intent_coverage",
]
