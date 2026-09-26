"""M26 — Optional LLM query decomposition.

Splits a research query into <= N subqueries. Output is validated,
bounded, deduplicated, normalized. Any provider-level failure falls
back to ``[normalized_query]``. The LLM only sees the query — never
project corpus.
"""
from __future__ import annotations

import logging
import re

from app.integrations.generation.base import (
    GenerationInvalidResponseError,
    GenerationProvider,
    GenerationProviderUnavailableError,
    GenerationRateLimitError,
    GenerationTimeoutError,
)

logger = logging.getLogger(__name__)

LLM_DECOMPOSITION_VERSION = "m26-decomp-v1"
MAX_SUBQUERIES = 5
MAX_SUBQUERY_CHARS = 400

_SYSTEM_PROMPT = (
    "You split a research query into at most 5 concise subqueries. "
    "Each subquery must be a standalone search phrase. "
    "Output only the subqueries, one per line. "
    "Do not number them. Do not add commentary. "
    "If the query is already simple, output it as a single line."
)

_LINE_CLEANUP = re.compile(r"^\s*(?:\d+[\.\)]|[-*])\s*")

_LLM_BOUNDARY_ERRORS = (
    GenerationTimeoutError,
    GenerationRateLimitError,
    GenerationProviderUnavailableError,
    GenerationInvalidResponseError,
)


def _parse_subqueries(text: str) -> list[str]:
    out: list[str] = []
    for raw in text.splitlines():
        line = _LINE_CLEANUP.sub("", raw).strip()
        if not line:
            continue
        if len(line) > MAX_SUBQUERY_CHARS:
            line = line[:MAX_SUBQUERY_CHARS].rstrip()
        out.append(line)
    return out


def _normalize_subqueries(
    normalized_query: str,
    subqueries: list[str],
) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for s in subqueries:
        key = s.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(s.strip())
        if len(result) >= MAX_SUBQUERIES:
            break
    if not result:
        result = [normalized_query]
    return result


def decompose_query(
    *,
    normalized_query: str,
    provider: GenerationProvider,
    temperature: float = 0.0,
    max_output_tokens: int = 256,
) -> tuple[list[str], list[str]]:
    """Return (subqueries, warnings).

    Only LLM-boundary errors are downgraded to fallback. Unexpected
    exceptions (programming bugs, DB errors) propagate.
    """
    warnings: list[str] = []
    try:
        result = provider.generate(
            system_prompt=_SYSTEM_PROMPT,
            user_prompt=normalized_query,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )
    except _LLM_BOUNDARY_ERRORS as exc:
        logger.warning(
            "llm_decomposition_fallback reason=%s",
            type(exc).__name__,
        )
        warnings.append("llm_decomposition_fallback")
        return [normalized_query], warnings

    parsed = _parse_subqueries(result.text or "")
    return _normalize_subqueries(normalized_query, parsed), warnings


__all__ = [
    "LLM_DECOMPOSITION_VERSION",
    "MAX_SUBQUERIES",
    "decompose_query",
]
