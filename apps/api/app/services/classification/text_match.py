"""M21 — Word-boundary aware alias matching.

Short aliases like "ai", "ml", "cs", "rct" must not match inside
arbitrary words ("said", "html", "success"). Aliases longer than
``_SHORT_ALIAS_THRESHOLD`` use plain substring matching for speed.
"""
from __future__ import annotations

import re
from functools import lru_cache

_SHORT_ALIAS_THRESHOLD = 5


@lru_cache(maxsize=2048)
def _wb_pattern(alias_lower: str) -> re.Pattern[str]:
    return re.compile(
        r"\b" + re.escape(alias_lower) + r"\b",
        re.IGNORECASE,
    )


def contains_alias(haystack: str, alias: str) -> bool:
    if not alias or not haystack:
        return False
    a = alias.strip()
    if len(a) <= _SHORT_ALIAS_THRESHOLD:
        return bool(_wb_pattern(a).search(haystack))
    return a.lower() in haystack.lower()
