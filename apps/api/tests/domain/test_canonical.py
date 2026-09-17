"""Canonical document + invariant tests."""
from __future__ import annotations

import pytest

from app.domain.extraction import (
    EXTRACTION_PIPELINE_VERSION,
    CanonicalDocument,
    CanonicalInvariantError,
    CanonicalPage,
    build_canonical_document,
    validate_canonical_document,
)
from app.domain.extraction_types import (
    ExtractedDocument,
    ExtractedPage,
)


def test_pipeline_version_is_non_empty_string() -> None:
    assert isinstance(EXTRACTION_PIPELINE_VERSION, str)
    assert EXTRACTION_PIPELINE_VERSION


def test_page_boundary_invariant() -> None:
    doc = ExtractedDocument(
        content_type="application/pdf",
        pages=[
            ExtractedPage(page_number=1, raw_text="Page one alpha beta"),
            ExtractedPage(page_number=2, raw_text="Page two gamma delta"),
        ],
    )
    canonical = build_canonical_document(doc)
    validate_canonical_document(canonical)
    for page in canonical.pages:
        assert (
            canonical.text[page.char_start : page.char_end] == page.text
        )


def test_empty_page_does_not_renumber() -> None:
    doc = ExtractedDocument(
        content_type="application/pdf",
        pages=[
            ExtractedPage(page_number=1, raw_text="First"),
            ExtractedPage(page_number=2, raw_text="   "),
            ExtractedPage(page_number=3, raw_text="Third"),
        ],
    )
    canonical = build_canonical_document(doc)
    assert [p.page_number for p in canonical.pages] == [1, 3]


def test_normalization_before_offsets() -> None:
    doc = ExtractedDocument(
        content_type="text/plain",
        pages=[
            ExtractedPage(
                page_number=None, raw_text="  Alpha\r\n\r\nBeta  "
            ),
        ],
    )
    canonical = build_canonical_document(doc)
    validate_canonical_document(canonical)
    assert "\r" not in canonical.text


def test_html_page_number_none() -> None:
    doc = ExtractedDocument(
        content_type="text/html",
        pages=[ExtractedPage(page_number=None, raw_text="<p>x</p>")],
    )
    canonical = build_canonical_document(doc)
    assert canonical.pages[0].page_number is None


def test_validator_rejects_bad_offsets() -> None:
    bad = CanonicalDocument(
        text="hello world",
        pages=[
            CanonicalPage(
                page_number=1,
                text="WRONG",
                char_start=0,
                char_end=5,
            )
        ],
    )
    with pytest.raises(CanonicalInvariantError):
        validate_canonical_document(bad)
