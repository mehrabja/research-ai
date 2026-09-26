"""M30 — Canonical CitationIdentity resolution (Unicode-safe)."""
from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.citation import CitationIdentity
from app.db.models.source import Source
from app.domain.citation import (
    REFERENCE_NORMALIZATION_VERSION,
    canonical_author,
    canonical_doi,
    canonical_title,
    identity_key_for,
)


@dataclass
class ResolvedIdentity:
    identity: CitationIdentity
    reused: bool


def _display_label(source: Source) -> str:
    authors = source.authors or []
    first = ""
    if authors:
        a = authors[0]
        if isinstance(a, str):
            first = a
        elif isinstance(a, dict):
            first = a.get("name") or a.get("family") or ""
    year = source.year
    title = (source.title or "").strip()
    parts: list[str] = []
    if first:
        parts.append(first)
    if year:
        parts.append(f"({year})")
    if title:
        parts.append(title[:120])
    return " — ".join(parts) if parts else (title or "Unknown")


def resolve_identity(
    db: Session, *, report_id: uuid.UUID, source: Source,
) -> ResolvedIdentity:
    key = identity_key_for(
        doi=source.doi,
        title=source.title,
        authors=source.authors,
        year=source.year,
    )
    existing = db.execute(
        select(CitationIdentity).where(
            CitationIdentity.report_id == report_id,
            CitationIdentity.identity_key == key,
        )
    ).scalar_one_or_none()
    if existing is not None:
        return ResolvedIdentity(identity=existing, reused=True)

    ident = CitationIdentity(
        report_id=report_id,
        identity_key=key,
        source_id=source.id,
        canonical_doi=canonical_doi(source.doi),
        canonical_title=canonical_title(source.title),
        canonical_first_author=canonical_author(source.authors),
        canonical_year=source.year,
        display_label=_display_label(source),
        normalization_version=REFERENCE_NORMALIZATION_VERSION,
        identity_meta={"m30_version": "m30.1"},
    )
    db.add(ident)
    db.flush()
    return ResolvedIdentity(identity=ident, reused=False)


__all__ = ["ResolvedIdentity", "resolve_identity"]
