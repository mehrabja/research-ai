"""M35 — Budget enforcement."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.config import Settings
from app.domain.orchestration import DEFAULT_BUDGET


@dataclass
class BudgetCheck:
    ok: bool
    reason: str | None = None


def _get_used(used: dict | None, key: str) -> int:
    if not used:
        return 0
    value = used.get(key, 0)
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def check_before_node(
    *,
    budget: dict,
    used: dict | None,
    node_count: int,
) -> BudgetCheck:
    max_nodes = int(
        budget.get("max_nodes", DEFAULT_BUDGET["max_nodes"])
    )
    if node_count >= max_nodes:
        return BudgetCheck(
            ok=False,
            reason=f"max_nodes_exceeded:{node_count}>={max_nodes}",
        )
    return BudgetCheck(ok=True)


def check_provider_call(
    *,
    budget: dict,
    used: dict | None,
    additional: int = 1,
) -> BudgetCheck:
    max_calls = int(
        budget.get(
            "max_provider_calls", DEFAULT_BUDGET["max_provider_calls"],
        )
    )
    current = _get_used(used, "provider_calls")
    if current + additional > max_calls:
        return BudgetCheck(
            ok=False,
            reason=(
                f"max_provider_calls_exceeded:"
                f"{current}+{additional}>{max_calls}"
            ),
        )
    return BudgetCheck(ok=True)


def accumulate(
    used: dict | None,
    *,
    provider_calls: int = 0,
    tokens: int = 0,
    evidence_volume: int = 0,
    generated_chars: int = 0,
) -> dict[str, Any]:
    out = dict(used or {})
    out["provider_calls"] = int(
        out.get("provider_calls", 0)
    ) + provider_calls
    out["tokens"] = int(out.get("tokens", 0)) + tokens
    out["evidence_volume"] = int(
        out.get("evidence_volume", 0)
    ) + evidence_volume
    out["generated_chars"] = int(
        out.get("generated_chars", 0)
    ) + generated_chars
    return out


def default_budget() -> dict[str, int]:
    return dict(DEFAULT_BUDGET)


__all__ = [
    "effective_budget",
    "BudgetCheck",
    "check_before_node",
    "check_provider_call",
    "accumulate",
    "default_budget",
]


def effective_budget(settings: Settings) -> dict[str, int]:
    budget = default_budget()
    budget["max_nodes"] = min(budget["max_nodes"], int(settings.orchestration_max_nodes))
    budget["max_retries_per_node"] = min(
        budget["max_retries_per_node"], int(settings.orchestration_max_retries_per_node)
    )
    budget["max_provider_calls"] = min(
        budget["max_provider_calls"], int(settings.orchestration_max_provider_calls)
    )
    budget["max_wall_clock_seconds"] = min(
        budget["max_wall_clock_seconds"], int(settings.orchestration_max_wall_clock_seconds)
    )
    budget["max_total_tokens"] = min(
        budget["max_total_tokens"], int(settings.orchestration_max_total_tokens)
    )
    budget["max_evidence_volume"] = min(
        budget["max_evidence_volume"], int(settings.orchestration_max_evidence_volume)
    )
    budget["max_generated_chars"] = min(
        budget["max_generated_chars"], int(settings.orchestration_max_generated_chars)
    )
    return budget
