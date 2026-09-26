"""M30 — Author-Year style helpers."""
from __future__ import annotations

from collections import defaultdict

from app.db.models.citation import CitationIdentity


def _last_name(identity: CitationIdentity) -> str:
    raw = (identity.canonical_first_author or "").strip()
    if not raw:
        return "Unknown"
    parts = raw.split()
    return parts[-1].capitalize() if len(parts) > 1 else parts[0].capitalize()


def order_alphabetical(
    identities: list[CitationIdentity],
) -> list[CitationIdentity]:
    return sorted(
        identities,
        key=lambda i: (
            _last_name(i).casefold(),
            i.canonical_year or 0,
            (i.canonical_title or ""),
            str(i.id),
        ),
    )


def format_author_year(
    identity: CitationIdentity,
    *,
    disambiguation_suffix: str = "",
) -> str:
    author = _last_name(identity)
    year = identity.canonical_year or "n.d."
    return f"{author}, {year}{disambiguation_suffix}"


def compute_disambiguation_suffixes(
    identities: list[CitationIdentity],
) -> dict[str, str]:
    """For identical (author, year), assign a/b/c/... deterministically."""
    by_key: dict[tuple[str, int], list[CitationIdentity]] = defaultdict(list)
    for i in identities:
        by_key[(_last_name(i).casefold(), i.canonical_year or 0)].append(i)
    suffixes: dict[str, str] = {}
    for _k, group in by_key.items():
        if len(group) == 1:
            suffixes[str(group[0].id)] = ""
            continue
        ordered = sorted(group, key=lambda i: (
            (i.canonical_title or ""), str(i.id),
        ))
        for idx, i in enumerate(ordered):
            suffix = chr(ord("a") + idx) if idx < 26 else f"z{idx}"
            suffixes[str(i.id)] = suffix
    return suffixes


__all__ = [
    "order_alphabetical",
    "format_author_year",
    "compute_disambiguation_suffixes",
]
