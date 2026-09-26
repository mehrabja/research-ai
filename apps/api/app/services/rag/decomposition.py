"""M26 — Deterministic query decomposition."""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.domain.retrieval_advanced import RetrievalIntent

_QUESTION_RE = re.compile(
    r"\?|^(what|how|why|when|where|which|who)\b", re.I
)
_COMPARE_RE = re.compile(
    r"\b(vs\.?|versus|compared|contrast|differ)\b", re.I
)
_CAUSAL_RE = re.compile(
    r"\b(cause|effect|impact|influence|affect)\b", re.I
)
_RECENT_RE = re.compile(r"\b(recent|latest|current|new|modern)\b", re.I)
_METHOD_RE = re.compile(
    r"\b(method|methodology|approach|technique)\b", re.I
)
_GAP_RE = re.compile(r"\b(gap|unexplored|missing|unclear)\b", re.I)
_LIMIT_RE = re.compile(r"\b(limitation|caveat|weakness|drawback)\b", re.I)
_COUNTER_RE = re.compile(r"\b(counter|contradict|oppos)\b", re.I)
_DEFINITION_RE = re.compile(r"\b(what is|define|definition)\b", re.I)
_SYNTHESIS_RE = re.compile(r"\b(review|synthes|survey|overview)\b", re.I)


@dataclass(frozen=True)
class DecomposedIntent:
    intent: str
    query: str
    weight: float


def decompose_deterministic(query: str) -> list[DecomposedIntent]:
    q = query.strip()
    if not q:
        return []

    intents: list[DecomposedIntent] = []

    intents.append(DecomposedIntent(
        intent=RetrievalIntent.BACKGROUND.value, query=q, weight=0.8,
    ))

    if _DEFINITION_RE.search(q):
        intents.append(DecomposedIntent(
            intent=RetrievalIntent.DEFINITION.value, query=q, weight=0.9,
        ))
    if _METHOD_RE.search(q):
        intents.append(DecomposedIntent(
            intent=RetrievalIntent.METHODOLOGY.value, query=q, weight=0.9,
        ))
    if _COMPARE_RE.search(q):
        intents.append(DecomposedIntent(
            intent=RetrievalIntent.COMPARISON.value, query=q, weight=1.0,
        ))
    if _CAUSAL_RE.search(q):
        intents.append(DecomposedIntent(
            intent=RetrievalIntent.CAUSAL_EVIDENCE.value, query=q,
            weight=1.0,
        ))
    if _RECENT_RE.search(q):
        intents.append(DecomposedIntent(
            intent=RetrievalIntent.RECENT_EVIDENCE.value, query=q,
            weight=1.0,
        ))
    if _GAP_RE.search(q):
        intents.append(DecomposedIntent(
            intent=RetrievalIntent.GAP.value, query=q, weight=0.9,
        ))
    if _LIMIT_RE.search(q):
        intents.append(DecomposedIntent(
            intent=RetrievalIntent.LIMITATION.value, query=q,
            weight=0.9,
        ))
    if _COUNTER_RE.search(q):
        intents.append(DecomposedIntent(
            intent=RetrievalIntent.COUNTER_EVIDENCE.value, query=q,
            weight=1.0,
        ))
    if _SYNTHESIS_RE.search(q):
        intents.append(DecomposedIntent(
            intent=RetrievalIntent.SYNTHESIS.value, query=q, weight=0.9,
        ))
    if _QUESTION_RE.search(q):
        intents.append(DecomposedIntent(
            intent=RetrievalIntent.EMPIRICAL_EVIDENCE.value,
            query=q, weight=1.0,
        ))

    seen: dict[str, DecomposedIntent] = {}
    for it in intents:
        seen.setdefault(it.intent, it)
    return list(seen.values())


__all__ = ["DecomposedIntent", "decompose_deterministic"]
