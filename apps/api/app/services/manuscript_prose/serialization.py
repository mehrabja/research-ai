"""M28.5 — Canonical structured ⇄ text serialization.

Stable, deterministic. No regex magic beyond paragraph/sentence
splitting that must be reproducible.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass, field

_SENT_TERMINATORS = "\\.!?؟۔"
_SENT_SPLIT_RE = re.compile(
    rf"(?<=[{_SENT_TERMINATORS}])\s+",
    re.UNICODE,
)
_WS_RE = re.compile(r"\s+", re.UNICODE)


def normalize_text(s: str) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFKC", s)
    return _WS_RE.sub(" ", s).strip()


def split_sentences(text: str) -> list[str]:
    if not text:
        return []
    parts = _SENT_SPLIT_RE.split(text)
    out: list[str] = []
    for p in parts:
        s = p.strip()
        if s:
            out.append(s)
    return out


def join_paragraphs(paragraphs: list[str]) -> str:
    return "\n\n".join(p for p in paragraphs if p)


def join_sentences(sentences: list[str]) -> str:
    return " ".join(s for s in sentences if s)


def word_count(text: str) -> int:
    """Language-neutral word count.

    Whitespace-delimited tokens. Unicode-safe. Deterministic.
    """
    if not text:
        return 0
    return len([t for t in _WS_RE.split(text) if t])


def paragraph_hash(text: str) -> str:
    return hashlib.sha256(
        normalize_text(text).encode("utf-8")
    ).hexdigest()


def sentence_hash(text: str) -> str:
    return hashlib.sha256(
        normalize_text(text).encode("utf-8")
    ).hexdigest()


@dataclass
class SentenceUnit:
    text: str
    char_start: int
    char_end: int
    evidence_refs: list[str] = field(default_factory=list)
    citation_refs: list[str] = field(default_factory=list)


@dataclass
class ParagraphUnit:
    ordinal: int
    text: str
    char_start: int
    char_end: int
    sentences: list[SentenceUnit] = field(default_factory=list)


@dataclass
class SectionUnit:
    section_key: str
    section_type: str
    display_order: int
    title: str
    paragraphs: list[ParagraphUnit] = field(default_factory=list)
    provenance: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        return join_paragraphs([p.text for p in self.paragraphs])

    @property
    def word_count(self) -> int:
        return word_count(self.text)

    @property
    def sentence_count(self) -> int:
        return sum(len(p.sentences) for p in self.paragraphs)

    @property
    def paragraph_count(self) -> int:
        return len(self.paragraphs)


def layout_section(unit: SectionUnit, cursor: int) -> tuple[int, int]:
    """Re-assign char_start/char_end for the section body.

    Returns (new_cursor, section_end).
    """
    pos = cursor
    for p in unit.paragraphs:
        p.char_start = pos
        for s in p.sentences:
            s.char_start = pos
            s.char_end = pos + len(s.text)
            pos += len(s.text) + 1  # single space separator
        # Rewrite paragraph text from sentences (canonical)
        p.text = join_sentences([s.text for s in p.sentences])
        if p.sentences:
            p.char_end = p.sentences[-1].char_end
        else:
            p.char_end = p.char_start
        pos += 2  # paragraph separator (\n\n)
    section_end = pos
    return pos, section_end


__all__ = [
    "normalize_text",
    "split_sentences",
    "join_paragraphs",
    "join_sentences",
    "word_count",
    "paragraph_hash",
    "sentence_hash",
    "SentenceUnit",
    "ParagraphUnit",
    "SectionUnit",
    "layout_section",
]
