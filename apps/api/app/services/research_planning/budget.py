"""M24 — Deterministic budget model."""
from __future__ import annotations

from dataclasses import dataclass

from app.core.exceptions import ResearchPlanBudgetInvalid


@dataclass(frozen=True)
class BudgetDefaults:
    max_search_calls: int = 20
    max_sources: int = 100
    max_retrieval_candidates: int = 500
    max_llm_tokens: int = 12000
    max_credits: float = 10.0


def normalize_section_allocations(
    raw: dict[str, float],
) -> dict[str, float]:
    if not raw:
        return {}
    for v in raw.values():
        if v < 0:
            raise ResearchPlanBudgetInvalid(
                "section allocation must be >= 0"
            )
    total = sum(raw.values())
    if total <= 0:
        raise ResearchPlanBudgetInvalid("total allocation must be > 0")
    normalized = {k: v / total for k, v in raw.items()}
    keys = list(normalized.keys())
    largest = max(keys, key=lambda k: normalized[k])
    drift = 1.0 - sum(normalized.values())
    normalized[largest] = max(0.0, normalized[largest] + drift)
    return normalized


def validate_budget(budget: dict) -> None:
    if not isinstance(budget, dict):
        raise ResearchPlanBudgetInvalid("budget must be an object")
    for key in (
        "max_search_calls",
        "max_sources",
        "max_retrieval_candidates",
        "max_llm_tokens",
    ):
        v = budget.get(key)
        if v is None:
            raise ResearchPlanBudgetInvalid(f"missing budget field {key}")
        if not isinstance(v, int) or v < 0:
            raise ResearchPlanBudgetInvalid(
                f"budget field {key} must be a non-negative int"
            )
    credits = budget.get("max_credits")
    if credits is None or not isinstance(credits, (int, float)) or credits < 0:
        raise ResearchPlanBudgetInvalid("max_credits must be >= 0")
    allocs = budget.get("section_allocations")
    if not isinstance(allocs, dict) or not allocs:
        raise ResearchPlanBudgetInvalid("section_allocations required")
    for k, v in allocs.items():
        if not isinstance(v, (int, float)) or v < 0:
            raise ResearchPlanBudgetInvalid(
                f"allocation {k} must be >= 0"
            )
    total = sum(allocs.values())
    if abs(total - 1.0) > 1e-6:
        raise ResearchPlanBudgetInvalid(
            f"section allocations must sum to 1.0 (got {total})"
        )


def build_default_budget(
    *,
    section_weights: dict[str, float],
    defaults: BudgetDefaults | None = None,
    word_target: int = 6000,
) -> dict:
    d = defaults or BudgetDefaults()
    allocations = normalize_section_allocations(section_weights)
    word_budget_by_section = {
        k: int(round(w * word_target)) for k, w in allocations.items()
    }
    return {
        "max_search_calls": d.max_search_calls,
        "max_sources": d.max_sources,
        "max_retrieval_candidates": d.max_retrieval_candidates,
        "max_llm_tokens": d.max_llm_tokens,
        "max_credits": d.max_credits,
        "section_allocations": allocations,
        "word_budget_by_section": word_budget_by_section,
        "word_target": word_target,
    }


def apply_budget_adjustments(
    budget: dict, adjustments: dict[str, float]
) -> dict:
    if not adjustments:
        return budget
    merged = dict(budget.get("section_allocations") or {})
    for k, v in adjustments.items():
        if k in merged:
            merged[k] = max(0.0, float(v))
    merged = normalize_section_allocations(merged)
    word_target = int(budget.get("word_target", 6000))
    new_budget = dict(budget)
    new_budget["section_allocations"] = merged
    new_budget["word_budget_by_section"] = {
        k: int(round(w * word_target)) for k, w in merged.items()
    }
    return new_budget
