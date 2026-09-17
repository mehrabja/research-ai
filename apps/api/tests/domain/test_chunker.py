"""Chunker tests including cross-page provenance."""
from __future__ import annotations

from app.domain.text_chunking import PageBoundary, WordTextChunker
from app.domain.text_normalization import normalize_text


def test_empty_text_yields_no_chunks() -> None:
    assert WordTextChunker(
        target_words=5, overlap_words=0
    ).chunk("") == []


def test_single_chunk_when_text_fits() -> None:
    chunks = WordTextChunker(
        target_words=10, overlap_words=0
    ).chunk("a b c")
    assert len(chunks) == 1
    assert chunks[0].content == "a b c"


def test_multiple_chunks_without_overlap() -> None:
    text = " ".join(f"w{i}" for i in range(12))
    chunks = WordTextChunker(
        target_words=5, overlap_words=0
    ).chunk(text)
    assert len(chunks) == 3
    assert [c.chunk_index for c in chunks] == [0, 1, 2]
    for c in chunks:
        assert text[c.char_start : c.char_end] == c.content


def test_cross_page_chunk_provenance() -> None:
    page1 = normalize_text("Page one alpha beta gamma delta")
    page2 = normalize_text("Page two epsilon zeta eta theta iota")
    canonical = f"{page1}\n\n{page2}"

    boundaries = [
        PageBoundary(page_number=1, char_start=0, char_end=len(page1)),
        PageBoundary(
            page_number=2,
            char_start=len(page1) + 2,
            char_end=len(canonical),
        ),
    ]

    chunker = WordTextChunker(
        target_words=6, overlap_words=0, page_boundaries=boundaries
    )
    chunks = chunker.chunk(canonical)

    for ch in chunks:
        assert ch.content == canonical[ch.char_start : ch.char_end]

    assert chunks[0].page_number == 1
    assert chunks[1].page_number == 2
