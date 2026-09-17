"""Chunk invariant tests."""
from __future__ import annotations

import pytest

from app.domain.extraction import (
    ChunkInvariantError,
    validate_chunks,
)
from app.domain.text_chunking import ChunkData, WordTextChunker


def _chunks(text: str) -> list[ChunkData]:
    return WordTextChunker(target_words=5, overlap_words=0).chunk(text)


def test_valid_chunks_pass() -> None:
    text = " ".join(f"w{i}" for i in range(30))
    chunks = _chunks(text)
    validate_chunks(chunks, text)


def test_non_contiguous_index_fails() -> None:
    text = "hello world"
    bad = [
        ChunkData(
            chunk_index=0,
            content="hello",
            char_start=0,
            char_end=5,
            page_number=None,
        ),
        ChunkData(
            chunk_index=2,
            content="world",
            char_start=6,
            char_end=11,
            page_number=None,
        ),
    ]
    with pytest.raises(ChunkInvariantError):
        validate_chunks(bad, text)


def test_content_mismatch_fails() -> None:
    text = "hello world"
    bad = [
        ChunkData(
            chunk_index=0,
            content="WRONG",
            char_start=0,
            char_end=5,
            page_number=None,
        ),
    ]
    with pytest.raises(ChunkInvariantError):
        validate_chunks(bad, text)


def test_invalid_offsets_fail() -> None:
    text = "hello world"
    bad = [
        ChunkData(
            chunk_index=0,
            content="x",
            char_start=5,
            char_end=5,
            page_number=None,
        ),
    ]
    with pytest.raises(ChunkInvariantError):
        validate_chunks(bad, text)
