"""M30 — Bibliography assembly.

Only identities actually cited by the current CitationRun.
Missing sources -> structured diagnostic, never silent skip.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.citation import CitationIdentity
from app.db.models.source import Source
from app.domain.citation import CitationStyle
from app.services.citation.styles.author_year import (
    compute_disambiguation_suffixes,
    format_author_year,
    order_alphabetical,
)
from app.services.citation.styles.numeric import (
    format_numeric,
    order_by_first_appearance,
)


@dataclass
class BibliographyEntry:
    citation_id: str
    source_id: str
    label: str
    rendered: str
    order: int
    display_key: str


@dataclass
class BibliographyResult:
    entries: list[BibliographyEntry]
    unresolved_identity_ids: list[str]


def _render_authors(authors: list | None) -> str:
    if not authors:
        return ""
    parts: list[str] = []
    for a in authors:
        if isinstance(a, str):
            parts.append(a)
        elif isinstance(a, dict):
            name = a.get("name") or a.get("family") or ""
            if name:
                parts.append(name)
    return "; ".join(parts)


def build_bibliography(
    db: Session,
    *,
    report_id,
    identities: list[CitationIdentity],
    first_seen: dict[str, int],
    style: str,
) -> BibliographyResult:
    # Resolve real sources; detect orphans (never silent).
    source_ids = [i.source_id for i in identities]
    sources_by_id: dict = {}
    if source_ids:
        rows = list(db.execute(
            select(Source).where(Source.id.in_(source_ids))
        ).scalars().all())
        sources_by_id = {s.id: s for s in rows}

    unresolved: list[str] = []
    usable: list[CitationIdentity] = []
    for ident in identities:
        if sources_by_id.get(ident.source_id) is None:
            unresolved.append(str(ident.id))
            continue
        usable.append(ident)

    if style == CitationStyle.AUTHOR_YEAR.value:
        ordered = order_alphabetical(usable)
        suffixes = compute_disambiguation_suffixes(usable)
        entries: list[BibliographyEntry] = []
        for idx, ident in enumerate(ordered, start=1):
            src = sources_by_id[ident.source_id]
            suffix = suffixes.get(str(ident.id), "")
            display_key = format_author_year(
                ident, disambiguation_suffix=suffix,
            )
            authors_str = _render_authors(src.authors)
            parts = [
                authors_str or "Unknown",
                f"({src.year})" if src.year else "(n.d.)",
                src.title or "Untitled",
                src.url or "",
                f"doi:{src.doi}" if src.doi else "",
            ]
            rendered = ". ".join(p for p in parts if p)
            entries.append(BibliographyEntry(
                citation_id=str(ident.id),
                source_id=str(ident.source_id),
                label=ident.display_label or "",
                rendered=rendered,
                order=idx,
                display_key=display_key,
            ))
        return BibliographyResult(
            entries=entries, unresolved_identity_ids=unresolved,
        )

    # numeric (first-appearance)
    ordered = order_by_first_appearance(usable, first_seen=first_seen)
    entries = []
    for idx, ident in enumerate(ordered, start=1):
        src = sources_by_id[ident.source_id]
        authors_str = _render_authors(src.authors)
        parts = [
            authors_str or "Unknown",
            f"({src.year})" if src.year else "(n.d.)",
            src.title or "Untitled",
            src.url or "",
            f"doi:{src.doi}" if src.doi else "",
        ]
        rendered = ". ".join(p for p in parts if p)
        entries.append(BibliographyEntry(
            citation_id=str(ident.id),
            source_id=str(ident.source_id),
            label=ident.display_label or "",
            rendered=rendered,
            order=idx,
            display_key=format_numeric(index=idx),
        ))
    return BibliographyResult(
        entries=entries, unresolved_identity_ids=unresolved,
    )


__all__ = [
    "BibliographyEntry",
    "BibliographyResult",
    "build_bibliography",
]
