"""M26 — Query normalization + deterministic fingerprint."""
from __future__ import annotations

import hashlib
import re
import unicodedata

_WHITESPACE = re.compile(r"\s+")
_PUNCT = re.compile(r"[!?.,;:]+")


def normalize_query(query: str) -> str:
    if not query:
        return ""
    text = unicodedata.normalize("NFKC", query)
    text = text.strip()
    text = _WHITESPACE.sub(" ", text)
    text = _PUNCT.sub(".", text)
    text = text.lower()
    return text

def query_hash(normalized_query: str) -> str:
    h = hashlib.sha256()
    h.update(normalized_query.encode("utf-8"))
    return h.hexdigest()[:32]


def normalize_and_hash(query: str) -> tuple[str, str]:
    n = normalize_query(query)
    return n, query_hash(n)


__all__ = ["normalize_query", "query_hash", "normalize_and_hash"]
