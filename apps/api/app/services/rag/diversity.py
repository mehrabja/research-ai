"""M26 — MMR-style diversity with deterministic tie-breaking."""
from __future__ import annotations

from app.services.rag.scoring import ScoredCandidate


def _source_key(s: ScoredCandidate) -> str:
    return str(s.candidate.source_id)


def _chunk_key(s: ScoredCandidate) -> str:
    return str(s.candidate.chunk_id)


def apply_mmr(
    scored: list[ScoredCandidate],
    *,
    lambda_: float,
    max_results: int,
) -> list[ScoredCandidate]:
    if not scored or max_results <= 0:
        return []
    lambda_ = max(0.0, min(1.0, lambda_))
    selected: list[ScoredCandidate] = []
    remaining = list(scored)

    remaining.sort(key=lambda s: (-s.final_score, _chunk_key(s)))
    selected.append(remaining.pop(0))

    while remaining and len(selected) < max_results:
        best_idx = 0
        best_value = float("-inf")
        best_tie = ""
        selected_sources = {_source_key(s) for s in selected}

        for i, cand in enumerate(remaining):
            redundancy = 0.0
            if _source_key(cand) in selected_sources:
                redundancy = 1.0
            mmr = (
                lambda_ * cand.final_score
                - (1.0 - lambda_) * redundancy
            )
            tie = _chunk_key(cand)
            if mmr > best_value or (mmr == best_value and tie < best_tie):
                best_value = mmr
                best_idx = i
                best_tie = tie

        chosen = remaining.pop(best_idx)
        chosen.diversity_penalty = (
            0.0 if _source_key(chosen) not in selected_sources else 1.0
        )
        if chosen.diversity_penalty == 0.0:
            chosen.reasons.append("diversity_selected")
        selected.append(chosen)

    return selected


__all__ = ["apply_mmr"]
