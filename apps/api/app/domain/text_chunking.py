"""Deterministic word-based chunking.

Rationale for word-based
------------------------
This milestone avoids introducing a tokenizer dependency. Word-based
chunking is a deterministic, well-defined approximation whose
interface (``TextChunker``) can be swapped for a token-aware
implementation in Milestone 9 without changing persistence or API
contracts.

Offsets
-------
All character offsets are half-open: ``[char_start, char_end)``.
``content == text[char_start:char_end]`` for every chunk. Chunks
overlap by ``overlap_words`` words; the overlap region has the same
character offsets as the tail of the previous chunk, which is correct
by design.

Page provenance
---------------
``page_number`` refers to the page containing ``char_start``. A chunk
spanning pages N and N+1 reports ``page_number == N``. Multi-page
provenance is out of scope for this milestone.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol

_WORD = re.compile(r"\S+")


@dataclass(frozen=True)
class ChunkData:
    chunk_index: int
    content: str
    char_start: int
    char_end: int
    page_number: int | None


@dataclass(frozen=True)
class PageBoundary:
    page_number: int
    char_start: int
    char_end: int


class TextChunker(Protocol):
    def chunk(self, text: str) -> list[ChunkData]: ...


class WordTextChunker:
    def __init__(
        self,
        *,
        target_words: int,
        overlap_words: int,
        page_boundaries: list[PageBoundary] | None = None,
    ) -> None:
        if target_words <= 0:
            raise ValueError("target_words must be positive")
        if overlap_words < 0:
            raise ValueError("overlap_words must be >= 0")
        if overlap_words >= target_words:
            raise ValueError("overlap_words must be < target_words")
        self._target = target_words
        self._overlap = overlap_words
        self._pages = page_boundaries or []

    def chunk(self, text: str) -> list[ChunkData]:
        if not text:
            return []

        word_matches = list(_WORD.finditer(text))
        if not word_matches:
            return []

        n = len(word_matches)
        chunks: list[ChunkData] = []
        chunk_index = 0
        i = 0
        while i < n:
            j = min(i + self._target, n)
            char_start = word_matches[i].start()
            char_end = word_matches[j - 1].end()
            content = text[char_start:char_end]
            chunks.append(
                ChunkData(
                    chunk_index=chunk_index,
                    content=content,
                    char_start=char_start,
                    char_end=char_end,
                    page_number=self._page_for_offset(char_start),
                )
            )
            chunk_index += 1
            if j >= n:
                break
            i = j - self._overlap
            if i <= 0:
                break

        return chunks

    def _page_for_offset(self, offset: int) -> int | None:
        for page in self._pages:
            if page.char_start <= offset < page.char_end:
                return page.page_number
        return None


__all__ = [
    "ChunkData",
    "PageBoundary",
    "TextChunker",
    "WordTextChunker",
]
