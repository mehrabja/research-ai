"""M16 — Translation preservation validation (pure)."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

_EVIDENCE_MARKER_RE = re.compile(r"\[E\d+\]")
_URL_RE = re.compile(r"https?://[^\s<>\(\)\[\]\{\}\"'`]+")
_DOI_RE = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Za-z0-9]+\b")
_NUMBER_RE = re.compile(r"(?<![\w.])\d+(?:[.,]\d+)?%?(?![\w.])")


@dataclass(frozen=True)
class TokenCounts:
    evidence_markers: Counter[str]
    urls: Counter[str]
    dois: Counter[str]
    numbers: Counter[str]


def extract_token_counts(text: str) -> TokenCounts:
    if text is None:
        raise ValueError("text must not be None")
    return TokenCounts(
        evidence_markers=Counter(_EVIDENCE_MARKER_RE.findall(text)),
        urls=Counter(_URL_RE.findall(text)),
        dois=Counter(_DOI_RE.findall(text)),
        numbers=Counter(_NUMBER_RE.findall(text)),
    )


@dataclass(frozen=True)
class PreservationSection:
    source_count: int
    target_count: int
    ok: bool
    missing: tuple[str, ...] = ()
    added: tuple[str, ...] = ()

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "source_count": self.source_count,
            "target_count": self.target_count,
            "ok": self.ok,
            "missing": list(self.missing),
            "added": list(self.added),
        }


@dataclass(frozen=True)
class GlossaryViolation:
    source_term: str
    required_target_term: str

    def to_jsonable(self) -> dict[str, str]:
        return {
            "source_term": self.source_term,
            "required_target_term": self.required_target_term,
        }


@dataclass(frozen=True)
class GlossarySection:
    ok: bool
    checked: int
    violations: tuple[GlossaryViolation, ...] = ()

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "checked": self.checked,
            "violations": [v.to_jsonable() for v in self.violations],
        }


@dataclass(frozen=True)
class TranslationPreservationResult:
    ok: bool
    evidence_markers: PreservationSection
    urls: PreservationSection
    dois: PreservationSection
    numbers: PreservationSection
    glossary: GlossarySection

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "evidence_markers": self.evidence_markers.to_jsonable(),
            "urls": self.urls.to_jsonable(),
            "dois": self.dois.to_jsonable(),
            "numbers": self.numbers.to_jsonable(),
            "glossary": self.glossary.to_jsonable(),
        }


def _compare(source: Counter[str], target: Counter[str]) -> PreservationSection:
    missing = tuple(sorted((source - target).elements()))
    added = tuple(sorted((target - source).elements()))
    ok = not missing and not added
    return PreservationSection(
        source_count=sum(source.values()),
        target_count=sum(target.values()),
        ok=ok,
        missing=missing,
        added=added,
    )


def check_glossary_terms(
    *,
    source_text: str,
    target_text: str,
    pairs: Iterable[tuple[str, str]],
) -> GlossarySection:
    checked = 0
    violations: list[GlossaryViolation] = []
    for src_term, tgt_term in pairs:
        if not src_term or not tgt_term:
            continue
        if src_term in source_text:
            checked += 1
            if tgt_term not in target_text:
                violations.append(
                    GlossaryViolation(
                        source_term=src_term,
                        required_target_term=tgt_term,
                    )
                )
    return GlossarySection(
        ok=not violations,
        checked=checked,
        violations=tuple(violations),
    )


def validate_translation_preservation(
    *,
    source_text: str,
    target_text: str,
    glossary_pairs: Iterable[tuple[str, str]] = (),
) -> TranslationPreservationResult:
    src = extract_token_counts(source_text)
    tgt = extract_token_counts(target_text)

    evidence = _compare(src.evidence_markers, tgt.evidence_markers)
    urls = _compare(src.urls, tgt.urls)
    dois = _compare(src.dois, tgt.dois)
    numbers = _compare(src.numbers, tgt.numbers)
    glossary = check_glossary_terms(
        source_text=source_text,
        target_text=target_text,
        pairs=glossary_pairs,
    )

    ok = (
        evidence.ok
        and urls.ok
        and dois.ok
        and numbers.ok
        and glossary.ok
    )
    return TranslationPreservationResult(
        ok=ok,
        evidence_markers=evidence,
        urls=urls,
        dois=dois,
        numbers=numbers,
        glossary=glossary,
    )
