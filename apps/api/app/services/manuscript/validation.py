"""M27 — Manuscript architecture validation (central)."""
from __future__ import annotations

from dataclasses import dataclass, field

from app.db.models.manuscript import (
    ManuscriptSection,
    ManuscriptSectionDependency,
)
from app.domain.manuscript import KNOWN_RETRIEVAL_INTENTS


@dataclass
class ManuscriptValidationResult:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def valid(self) -> bool:
        return not self.errors

    def as_dict(self) -> dict:
        return {
            "validation_status": "valid" if self.valid() else "invalid",
            "validation_errors": list(self.errors),
            "warnings": list(self.warnings),
        }


def _has_cycle(nodes: list[str], edges: list[tuple[str, str]]) -> bool:
    adj: dict[str, list[str]] = {n: [] for n in nodes}
    for u, v in edges:
        adj.setdefault(u, []).append(v)
        adj.setdefault(v, [])
    WHITE, GRAY, BLACK = 0, 1, 2
    color = dict.fromkeys(adj, WHITE)

    def dfs(u: str) -> bool:
        color[u] = GRAY
        for v in adj[u]:
            if color[v] == GRAY:
                return True
            if color[v] == WHITE and dfs(v):
                return True
        color[u] = BLACK
        return False

    return any(color[n] == WHITE and dfs(n) for n in adj)


def validate_persisted_manuscript(
    *,
    sections: list[ManuscriptSection],
    dependencies: list[ManuscriptSectionDependency],
    word_target: int,
    budget_tolerance: float = 0.10,
) -> ManuscriptValidationResult:
    res = ManuscriptValidationResult()

    if not sections:
        res.errors.append("no sections")
        return res

    keys = [s.section_key for s in sections]
    if len(keys) != len(set(keys)):
        res.errors.append("duplicate section keys")

    orders = sorted(s.display_order for s in sections)
    if orders != list(range(len(orders))):
        res.errors.append("display_order is not a continuous 0..N-1 sequence")

    total_words = 0
    for s in sections:
        if not s.title:
            res.errors.append(f"section {s.section_key}: missing title")
        if s.required and s.word_budget <= 0:
            res.errors.append(
                f"required section {s.section_key}: word_budget must be > 0"
            )
        total_words += int(s.word_budget)

        contract = s.research_contract or {}
        intents = contract.get("retrieval_intents") or []
        for i in intents:
            if i not in KNOWN_RETRIEVAL_INTENTS:
                res.errors.append(
                    f"section {s.section_key}: unknown intent {i}"
                )
        for req in contract.get("evidence_requirements") or []:
            if req.get("required"):
                req_intents = req.get("retrieval_intents") or []
                if not req_intents:
                    res.errors.append(
                        f"required requirement "
                        f"{req.get('requirement_key')} in section "
                        f"{s.section_key} has no intent mapping"
                    )
                for i in req_intents:
                    if i not in KNOWN_RETRIEVAL_INTENTS:
                        res.errors.append(
                            f"section {s.section_key}: unknown intent "
                            f"{i} in requirement "
                            f"{req.get('requirement_key')}"
                        )

    if word_target > 0:
        diff = abs(total_words - word_target) / word_target
        if diff > budget_tolerance:
            res.errors.append(
                f"budget sum {total_words} differs from word_target "
                f"{word_target} by {diff:.2%}"
            )

    by_id = {s.id: s.section_key for s in sections}
    edges: list[tuple[str, str]] = []
    seen_edges: set[tuple[str, str]] = set()
    for d in dependencies:
        up = by_id.get(d.upstream_section_id)
        down = by_id.get(d.downstream_section_id)
        if up is None or down is None:
            res.errors.append("dependency endpoint not in version")
            continue
        if up == down:
            res.errors.append(f"self-dependency: {up}")
        if (up, down) in seen_edges:
            res.errors.append(f"duplicate dependency edge: {up}->{down}")
        seen_edges.add((up, down))
        edges.append((up, down))

    if _has_cycle(keys, edges):
        res.errors.append("dependency cycle detected")

    return res


__all__ = ["ManuscriptValidationResult", "validate_persisted_manuscript"]
