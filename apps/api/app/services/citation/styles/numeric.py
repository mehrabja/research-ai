"""M30 — Numeric style helpers (first-appearance order driven)."""
from __future__ import annotations

from app.db.models.citation import CitationIdentity


def order_by_first_appearance(
    identities: list[CitationIdentity],
    *,
    first_seen: dict[str, int],
) -> list[CitationIdentity]:
    """Sort by first manuscript appearance. Deterministic."""
    return sorted(
        identities,
        key=lambda i: (first_seen.get(str(i.id), 10**9), str(i.id)),
    )


def format_numeric(*, index: int) -> str:
    return f"[{index}]"


__all__ = ["order_by_first_appearance", "format_numeric"]
