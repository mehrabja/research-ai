"""Domain: canonical document builder, pipeline version, and invariants.

This module is pure domain logic:
  * no ORM / DB / HTTP imports;
  * no imports from ``app.integrations.*``;
  * no imports from ``app.services.*``.

It owns:
  * ``EXTRACTION_PIPELINE_VERSION`` — the single source of truth;
  * ``CanonicalPage`` / ``CanonicalDocument``;
  * ``build_canonical_document`` — the canonicalizer;
  * ``validate_canonical_document``, ``validate_chunks``,
    ``validate_hash_invariant`` — hard, fail-closed checks.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.domain.extraction_types import ExtractedDocument
from app.domain.text_chunking import ChunkData, PageBoundary
from app.domain.text_hashing import compute_content_hash
from app.domain.text_normalization import normalize_text

# ---------------------------------------------------------------------------
# Pipeline version — single source of truth
# ---------------------------------------------------------------------------
# Bump this whenever any of the following changes in a way that should
# trigger a rebuild of already-extracted sources:
#   * normalization algorithm
#   * canonicalization rules
#   * chunking algorithm / defaults
#   * extractor behavior
#   * provenance semantics
EXTRACTION_PIPELINE_VERSION: str = "m8.1"


# ---------------------------------------------------------------------------
# Canonical data model
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class CanonicalPage:
    """One page of the canonical (normalized) document.

    Empty pages are skipped but do not renumber subsequent pages.
    ``char_start``/``char_end`` are half-open offsets into the parent
    ``CanonicalDocument.text``.
    """

    page_number: int | None
    text: str
    char_start: int
    char_end: int


@dataclass(frozen=True)
class CanonicalDocument:
    text: str
    pages: list[CanonicalPage] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------
def build_canonical_document(
    extracted: ExtractedDocument,
) -> CanonicalDocument:
    """Normalize each page, concatenate non-empty pages with a blank
    line, and return canonical text plus exact page boundaries.

    The boundary offsets refer to the *already normalized*
    concatenated string, so chunk offsets derived from the same
    string map back to a page without additional translation.
    """
    parts: list[str] = []
    pages: list[CanonicalPage] = []
    cursor = 0

    for raw_page in extracted.pages:
        normalized = normalize_text(raw_page.raw_text)
        if not normalized:
            continue

        if parts:
            parts.append("\n\n")
            cursor += 2

        start = cursor
        parts.append(normalized)
        cursor += len(normalized)

        pages.append(
            CanonicalPage(
                page_number=raw_page.page_number,
                text=normalized,
                char_start=start,
                char_end=cursor,
            )
        )

    return CanonicalDocument(text="".join(parts), pages=pages)


def to_page_boundaries(
    canonical: CanonicalDocument,
) -> list[PageBoundary]:
    """Return ``PageBoundary`` objects compatible with the chunker.

    Pages without a real page number (HTML, plain text) are omitted so
    the chunker does not attach a fake page number.
    """
    return [
        PageBoundary(
            page_number=p.page_number,
            char_start=p.char_start,
            char_end=p.char_end,
        )
        for p in canonical.pages
        if p.page_number is not None
    ]


# ---------------------------------------------------------------------------
# Invariant enforcement
# ---------------------------------------------------------------------------
class CanonicalInvariantError(RuntimeError):
    """A canonical document violated one of its guarantees."""


class ChunkInvariantError(RuntimeError):
    """A chunker output violated one of its guarantees."""


def validate_canonical_document(canonical: CanonicalDocument) -> None:
    """Fail-closed check on a canonical document."""
    total = len(canonical.text)
    prev_end = -1
    for page in canonical.pages:
        if not (0 <= page.char_start < page.char_end <= total):
            raise CanonicalInvariantError(
                f"page {page.page_number!r} has invalid offsets "
                f"[{page.char_start}, {page.char_end})"
            )
        if page.char_start < prev_end:
            raise CanonicalInvariantError(
                "canonical pages are not in increasing order"
            )
        if canonical.text[page.char_start : page.char_end] != page.text:
            raise CanonicalInvariantError(
                f"page {page.page_number!r} content does not match its "
                "character range"
            )
        prev_end = page.char_end


def validate_chunks(chunks: list[ChunkData], canonical_text: str) -> None:
    """Fail-closed check on chunker output before persistence."""
    total = len(canonical_text)
    for expected, chunk in enumerate(chunks):
        if chunk.chunk_index != expected:
            raise ChunkInvariantError(
                f"chunk index {chunk.chunk_index} is not the expected "
                f"contiguous value {expected}"
            )
        if not (0 <= chunk.char_start < chunk.char_end <= total):
            raise ChunkInvariantError(
                f"chunk {chunk.chunk_index} has invalid offsets "
                f"[{chunk.char_start}, {chunk.char_end})"
            )
        if canonical_text[chunk.char_start : chunk.char_end] != chunk.content:
            raise ChunkInvariantError(
                f"chunk {chunk.chunk_index} content does not match its "
                "character range"
            )


def validate_hash_invariant(
    canonical_text: str, expected_hash: str
) -> None:
    """Fail-closed check that ``expected_hash == sha256(text)``."""
    actual = compute_content_hash(canonical_text)
    if actual != expected_hash:
        raise CanonicalInvariantError(
            "content hash does not match canonical text"
        )


__all__ = [
    "EXTRACTION_PIPELINE_VERSION",
    "CanonicalDocument",
    "CanonicalPage",
    "CanonicalInvariantError",
    "ChunkInvariantError",
    "build_canonical_document",
    "to_page_boundaries",
    "validate_canonical_document",
    "validate_chunks",
    "validate_hash_invariant",
]
