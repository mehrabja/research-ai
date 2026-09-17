"""Domain-owned extraction data types.

These types form the contract between extraction *producers*
(``integrations.documents.extractors``) and extraction *consumers*
(``domain.extraction``).

Dependency direction:

    integrations  ──►  domain.extraction_types  ◄──  services

Never the reverse. Nothing in ``domain`` imports from ``integrations``,
``services``, ``db``, or ``api``.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ExtractedPage:
    """One logical page of source text, raw and un-normalized.

    ``page_number`` is the *real* page number (1-based for PDF) or
    ``None`` for formats without a page concept (HTML, plain text).
    Extractors must never renumber or coalesce pages.
    """

    page_number: int | None
    raw_text: str


@dataclass(frozen=True)
class ExtractedDocument:
    """The raw output of an extractor.

    Extractors produce this; the canonicalizer consumes it. No
    character offsets, hashes, or normalized text live here.
    """

    content_type: str
    pages: list[ExtractedPage]
    metadata: dict[str, object] = field(default_factory=dict)


__all__ = ["ExtractedDocument", "ExtractedPage"]
