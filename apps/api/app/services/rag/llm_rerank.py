"""M26 — Optional LLM reranking.

The LLM receives a bounded candidate list and returns a reordering.
It cannot inject candidates, change source ids, or bypass plan
filters. Unknown/malformed output falls back to deterministic order.
"""
from __future__ import annotations

import json
import logging

from app.integrations.generation.base import (
    GenerationInvalidResponseError,
    GenerationProvider,
    GenerationProviderUnavailableError,
    GenerationRateLimitError,
    GenerationTimeoutError,
)
from app.security.trust_boundary import wrap_untrusted_text

logger = logging.getLogger(__name__)

LLM_RERANK_VERSION = "m26-rerank-v1"
MAX_RERANK_CANDIDATES = 20
MAX_SNIPPET_CHARS = 400

_SYSTEM_PROMPT = (
    "You rank candidate evidence chunks for a research query. "
    "Return ONLY a JSON array of chunk_id strings, best first. "
    "Use only chunk_ids from the provided list. "
    "Do not invent ids. Do not add commentary."
)

_LLM_BOUNDARY_ERRORS = (
    GenerationTimeoutError,
    GenerationRateLimitError,
    GenerationProviderUnavailableError,
    GenerationInvalidResponseError,
)


def _build_user_prompt(query: str, items: list[dict]) -> str:
    lines = [f"Query: {query}", "", "Candidates:"]
    for it in items:
        snippet = (it["snippet"] or "")[:MAX_SNIPPET_CHARS]
        lines.append(f"- chunk_id={it['chunk_id']} score={it['score']:.4f}")
        lines.append("  snippet:")
        lines.append(wrap_untrusted_text(snippet, max_chars=MAX_SNIPPET_CHARS))
    return "\n".join(lines)


def _parse_order(text: str) -> list[str]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()
    try:
        data = json.loads(cleaned)
    except (ValueError, TypeError):
        return []
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, str)]


def rerank_candidates(
    *,
    normalized_query: str,
    candidates: list[dict],
    provider: GenerationProvider,
    temperature: float = 0.0,
    max_output_tokens: int = 512,
) -> tuple[list[dict], list[str]]:
    """Return (reordered_candidates, warnings).

    ``candidates`` items: {chunk_id: str, score: float, snippet: str}.
    Fallback returns the input order unchanged.
    """
    warnings: list[str] = []
    if not candidates:
        return candidates, warnings

    bounded = candidates[:MAX_RERANK_CANDIDATES]
    tail = candidates[MAX_RERANK_CANDIDATES:]

    valid_ids = {c["chunk_id"] for c in bounded}
    by_id = {c["chunk_id"]: c for c in bounded}

    try:
        result = provider.generate(
            system_prompt=_SYSTEM_PROMPT,
            user_prompt=_build_user_prompt(normalized_query, bounded),
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )
    except _LLM_BOUNDARY_ERRORS as exc:
        logger.warning(
            "llm_rerank_fallback reason=%s", type(exc).__name__
        )
        warnings.append("llm_rerank_fallback")
        return candidates, warnings

    order = _parse_order(result.text or "")
    if not order:
        warnings.append("llm_rerank_fallback")
        return candidates, warnings

    seen: set[str] = set()
    reordered: list[dict] = []
    for cid in order:
        if cid not in valid_ids or cid in seen:
            warnings.append("llm_rerank_fallback")
            return candidates, warnings
        seen.add(cid)
        reordered.append(by_id[cid])

    for c in bounded:
        if c["chunk_id"] not in seen:
            reordered.append(c)
    reordered.extend(tail)
    return reordered, warnings


__all__ = [
    "LLM_RERANK_VERSION",
    "MAX_RERANK_CANDIDATES",
    "rerank_candidates",
]
