"""M14 — Preservation validation (pure)."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

_EVIDENCE_MARKER_RE = re.compile(r"\[E\d+\]")
_URL_RE = re.compile(r"https?://[^\s<>\(\)\[\]\{\}\"'`]+")
_DOI_RE = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Za-z0-9]+\b")
_NUMBER_RE = re.compile(r"(?<![\w.])\d+(?:\.\d+)?%?(?![\w.])")


@dataclass(frozen=True)
class ProtectedTokenSnapshot:
    evidence_markers: tuple[str, ...]
    urls: tuple[str, ...]
    dois: tuple[str, ...]
    numbers: tuple[str, ...]
    glossary_terms: tuple[str, ...]

    def counters(self) -> Mapping[str, Counter[str]]:
        return {
            "evidence_markers": Counter(self.evidence_markers),
            "urls": Counter(self.urls),
            "dois": Counter(self.dois),
            "numbers": Counter(self.numbers),
            "glossary_terms": Counter(self.glossary_terms),
        }


def _unique(items: Iterable[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    out: list[str] = []
    for x in items:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return tuple(out)


def extract_protected_tokens(
    text: str, *, glossary_terms: Iterable[str] = ()
) -> ProtectedTokenSnapshot:
    if text is None:
        raise ValueError("text must not be None")
    glossary_hits = [t for t in glossary_terms if t and t in text]
    return ProtectedTokenSnapshot(
        evidence_markers=_unique(_EVIDENCE_MARKER_RE.findall(text)),
        urls=_unique(_URL_RE.findall(text)),
        dois=_unique(_DOI_RE.findall(text)),
        numbers=_unique(_NUMBER_RE.findall(text)),
        glossary_terms=_unique(glossary_hits),
    )


@dataclass(frozen=True)
class PreservationViolation:
    category: str
    detail: str


@dataclass(frozen=True)
class PreservationResult:
    ok: bool
    violations: tuple[PreservationViolation, ...]
    before: ProtectedTokenSnapshot
    after: ProtectedTokenSnapshot

    def to_jsonable(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "violations": [
                {"category": v.category, "detail": v.detail} for v in self.violations
            ],
        }


_LABELS = {
    "evidence_markers": "evidence marker",
    "urls": "URL",
    "dois": "DOI",
    "numbers": "numeric token",
    "glossary_terms": "locked glossary term",
}


def _diff(cat: str, b: Counter[str], a: Counter[str]) -> list[PreservationViolation]:
    label = _LABELS.get(cat, cat)
    v: list[PreservationViolation] = []
    for tok, n in sorted((b - a).items()):
        v.append(PreservationViolation(cat, f"{label} removed: {tok!r} (missing {n})"))
    for tok, n in sorted((a - b).items()):
        v.append(PreservationViolation(cat, f"{label} introduced: {tok!r} (added {n})"))
    return v


def validate_preservation(
    before: ProtectedTokenSnapshot, after: ProtectedTokenSnapshot
) -> PreservationResult:
    bc = before.counters()
    ac = after.counters()
    violations: list[PreservationViolation] = []
    for cat in ("evidence_markers", "urls", "dois", "numbers", "glossary_terms"):
        violations.extend(_diff(cat, bc[cat], ac[cat]))
    return PreservationResult(
        ok=not violations, violations=tuple(violations), before=before, after=after
    )
