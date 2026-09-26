"""M32 — Meaning-preservation fingerprinting + diff."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

from app.domain.humanization_m32 import (
    PRESERVATION_CATEGORIES,
    PreservationOutcome,
)

# Citation markers like [1], [12], [1,2], [1-3], (Author, 2020)
_NUMERIC_CITE_RE = re.compile(r"\[\s*\d+(?:\s*[,\-]\s*\d+)*\s*\]")
_PAREN_YEAR_CITE_RE = re.compile(
    r"\([^()]{1,120}?,\s*(?:19|20)\d{2}[a-z]?\)"
)

# Numbers (with optional decimal + sign + thousands separators)
_NUMBER_RE = re.compile(
    r"(?<![A-Za-z0-9_])[-+]?\d{1,3}(?:,\d{3})*(?:\.\d+)?"
    r"(?:[eE][-+]?\d+)?(?![A-Za-z0-9_])"
)

# Units directly after numbers
_UNIT_RE = re.compile(
    r"\b(?:ms|s|sec|seconds?|min|minutes?|h|hours?|"
    r"kb|mb|gb|tb|b|bytes?|"
    r"hz|khz|mhz|ghz|"
    r"mm|cm|m|km|"
    r"mg|g|kg|"
    r"ml|l|"
    r"fps|rps|qps|tps|"
    r"%|pp|"
    r"n|"
    r"flops|gflops|tflops)\b",
    re.IGNORECASE,
)

# Very light named-entity detection: capitalised multiword runs
_NE_RE = re.compile(r"\b[A-Z][a-zA-Z0-9\-]+(?:\s+[A-Z][a-zA-Z0-9\-]+)+\b")

# Equation-ish identifiers: single letters with subscripts
_EQ_ID_RE = re.compile(r"\b[A-Za-z]_[A-Za-z0-9]+\b")

# M30-style reference markers
_REF_MARKER_RE = re.compile(r"\{\{ref:[^}]+\}\}")


def _normalise(s: str) -> str:
    return unicodedata.normalize("NFKC", s or "")


def _collect(pattern: re.Pattern[str], text: str) -> list[str]:
    return [m.group(0) for m in pattern.finditer(text)]


def _technical_terms(text: str) -> list[str]:
    """Light heuristic: tokens with digits or underscore."""
    out: list[str] = []
    for tok in re.findall(r"\b[A-Za-z][A-Za-z0-9_\-]*\b", text):
        if "_" in tok or any(ch.isdigit() for ch in tok):
            out.append(tok)
    return out


@dataclass
class Fingerprint:
    citations: list[str] = field(default_factory=list)
    numbers: list[str] = field(default_factory=list)
    units: list[str] = field(default_factory=list)
    named_entities: list[str] = field(default_factory=list)
    technical_terms: list[str] = field(default_factory=list)
    equations: list[str] = field(default_factory=list)
    section_structure: list[str] = field(default_factory=list)
    reference_markers: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "citations": self.citations,
            "numbers": self.numbers,
            "units": self.units,
            "named_entities": self.named_entities,
            "technical_terms": self.technical_terms,
            "equations": self.equations,
            "section_structure": self.section_structure,
            "reference_markers": self.reference_markers,
        }


def build_fingerprint(
    text: str,
    *,
    section_structure: list[str] | None = None,
) -> Fingerprint:
    t = _normalise(text)
    return Fingerprint(
        citations=(
            _collect(_NUMERIC_CITE_RE, t)
            + _collect(_PAREN_YEAR_CITE_RE, t)
        ),
        numbers=_collect(_NUMBER_RE, t),
        units=_collect(_UNIT_RE, t),
        named_entities=_collect(_NE_RE, t),
        technical_terms=_technical_terms(t),
        equations=_collect(_EQ_ID_RE, t),
        section_structure=list(section_structure or []),
        reference_markers=_collect(_REF_MARKER_RE, t),
    )


@dataclass
class PreservationResult:
    outcome: str
    drift_by_category: dict[str, dict[str, list[str]]]
    preservation_ratio: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "outcome": self.outcome,
            "drift_by_category": self.drift_by_category,
            "preservation_ratio": self.preservation_ratio,
        }


def compare_fingerprints(
    before: Fingerprint,
    after: Fingerprint,
) -> PreservationResult:
    drift: dict[str, dict[str, list[str]]] = {}
    total = 0
    preserved = 0

    for category in PRESERVATION_CATEGORIES:
        b = list(getattr(before, category))
        a = list(getattr(after, category))
        b_sorted = sorted(b)
        a_sorted = sorted(a)
        missing = list(b_sorted)
        for item in a_sorted:
            if item in missing:
                missing.remove(item)
        added = list(a_sorted)
        for item in b_sorted:
            if item in added:
                added.remove(item)
        total += len(b_sorted)
        preserved += len(b_sorted) - len(missing)
        if missing or added:
            drift[category] = {
                "missing": missing,
                "added": added,
            }

    if total == 0:
        ratio = 1.0
        outcome = PreservationOutcome.OK.value
    else:
        ratio = preserved / total
        outcome = (
            PreservationOutcome.OK.value
            if not drift
            else PreservationOutcome.DRIFT_DETECTED.value
        )

    return PreservationResult(
        outcome=outcome,
        drift_by_category=drift,
        preservation_ratio=round(ratio, 4),
    )


__all__ = [
    "Fingerprint",
    "build_fingerprint",
    "PreservationResult",
    "compare_fingerprints",
]
