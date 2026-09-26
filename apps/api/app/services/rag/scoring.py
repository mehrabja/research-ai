"""M26 — Hybrid scoring + deterministic ranking."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.db.models.source import Source
from app.services.rag.candidates import Candidate


@dataclass
class ScoredCandidate:
    candidate: Candidate
    final_score: float
    vector_score: float | None = None
    lexical_score: float | None = None
    graph_score: float | None = None
    memory_score: float | None = None
    quality_score: float | None = None
    diversity_penalty: float | None = None
    reasons: list[str] = field(default_factory=list)
    graph_distance: int | None = None
    memory_match: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)


def _clamp(v: float) -> float:
    return max(0.0, min(1.0, v))


def quality_score_for_source(source: Source | None) -> float | None:
    if source is None:
        return None
    if source.source_quality is not None:
        try:
            return _clamp(float(source.source_quality))
        except (TypeError, ValueError):
            return None
    status = (source.status or "").lower()
    if status in ("structured_full_text", "full_text"):
        return 0.85
    if status == "abstract_only":
        return 0.55
    if status == "metadata_only":
        return 0.35
    if status == "extraction_failed":
        return 0.15
    return None


def score_candidates(
    candidates: list[Candidate],
    *,
    sources_by_id: dict,
) -> list[ScoredCandidate]:
    out: list[ScoredCandidate] = []
    for c in candidates:
        src = sources_by_id.get(c.source_id)
        q = quality_score_for_source(src)

        v_sim = (
            1.0 - c.vector_distance
            if c.vector_distance is not None else None
        )
        if v_sim is not None:
            v_sim = _clamp(v_sim)

        l_norm = (
            _clamp(c.lexical_score / 2.0)
            if c.lexical_score is not None else None
        )

        g_score: float | None = None
        g_dist: int | None = None
        if c.stage.startswith("graph:d"):
            try:
                g_dist = int(c.stage.split("d", 1)[1])
                g_score = _clamp(1.0 / (1.0 + g_dist))
            except (ValueError, IndexError):
                g_score = None

        base_parts: list[float] = [c.fusion_score]
        reasons: list[str] = ["hybrid_fusion"]
        if v_sim is not None:
            base_parts.append(v_sim)
            reasons.append("vector_match")
        if l_norm is not None:
            base_parts.append(l_norm)
            reasons.append("lexical_match")
        if g_score is not None:
            base_parts.append(g_score)
            reasons.append("graph_neighbor")
        if q is not None:
            base_parts.append(q)
            reasons.append("source_quality")

        final = sum(base_parts) / max(1, len(base_parts))

        out.append(ScoredCandidate(
            candidate=c,
            final_score=final,
            vector_score=v_sim,
            lexical_score=l_norm,
            graph_score=g_score,
            memory_score=None,
            quality_score=q,
            reasons=reasons,
            graph_distance=g_dist,
        ))
    out.sort(key=lambda s: (-s.final_score, str(s.candidate.chunk_id)))
    return out


__all__ = [
    "ScoredCandidate",
    "score_candidates",
    "quality_score_for_source",
]
