"""M30 — Advanced Citation & Reference Engine domain primitives (pure)."""
from __future__ import annotations

import hashlib
import re
import unicodedata
from enum import StrEnum

M30_VERSION = "m30.1"
CLAIM_EXTRACTION_VERSION = "m30-claim-v1"
REFERENCE_NORMALIZATION_VERSION = "m30-refnorm-v1"

CLAIM_SUPPORT_THRESHOLD = 0.5


class ClaimType(StrEnum):
    BACKGROUND = "background"
    DEFINITION = "definition"
    METHOD = "method"
    RESULT = "result"
    COMPARISON = "comparison"
    CAUSAL = "causal"
    LIMITATION = "limitation"
    SYNTHESIS = "synthesis"
    CONCLUSION = "conclusion"
    TECHNICAL = "technical"


class EvidenceType(StrEnum):
    M28_EVIDENCE = "m28_evidence"
    M29_TECHNICAL_FACT = "m29_technical_fact"
    M29_EXPERIMENT_RESULT = "m29_experiment_result"
    M29_METRIC = "m29_metric"


class SupportLevel(StrEnum):
    SUPPORTS = "supports"
    PARTIALLY_SUPPORTS = "partially_supports"
    CONTRADICTS = "contradicts"
    CONTEXT_ONLY = "context_only"


class CitationRelationType(StrEnum):
    SUPPORTS = "supports"
    PARTIALLY_SUPPORTS = "partially_supports"
    CONTRADICTS = "contradicts"
    CONTEXT_ONLY = "context_only"
    METHODS_REFERENCE = "methods_reference"
    BACKGROUND_REFERENCE = "background_reference"


class CitationStyle(StrEnum):
    NUMERIC = "numeric"
    AUTHOR_YEAR = "author_year"


class CitationRunStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class ClaimStatus(StrEnum):
    EXTRACTED = "extracted"
    MAPPED = "mapped"
    UNSUPPORTED = "unsupported"


CLAIM_TYPES = tuple(t.value for t in ClaimType)
EVIDENCE_TYPES = tuple(t.value for t in EvidenceType)
SUPPORT_LEVELS = tuple(s.value for s in SupportLevel)
CITATION_RELATION_TYPES = tuple(r.value for r in CitationRelationType)
CITATION_STYLES = tuple(s.value for s in CitationStyle)
CITATION_RUN_STATUSES = tuple(s.value for s in CitationRunStatus)
CLAIM_STATUSES = tuple(s.value for s in ClaimStatus)

_WS_RE = re.compile(r"\s+")
_PUNCT_STRIP_RE = re.compile(r"[.,;:!?\"'()\[\]{}<>—–\-]+")


def normalize_text(s: str) -> str:
    """Unicode-safe whitespace + quote normalization. No ASCII folding."""
    if not s:
        return ""
    s = unicodedata.normalize("NFKC", s)
    s = s.replace("\u2018", "'").replace("\u2019", "'")
    s = s.replace("\u201C", '"').replace("\u201D", '"')
    s = s.replace("\u2013", "-").replace("\u2014", "-")
    return _WS_RE.sub(" ", s).strip()


def canonical_doi(doi: str | None) -> str | None:
    if not doi:
        return None
    s = doi.strip().lower()
    for prefix in (
        "https://doi.org/", "http://doi.org/",
        "https://dx.doi.org/", "http://dx.doi.org/",
        "doi:", "https://www.doi.org/",
    ):
        if s.startswith(prefix):
            s = s[len(prefix):]
            break
    s = s.strip()
    return s or None


def canonical_title(title: str | None) -> str | None:
    """Unicode-safe. Preserves Persian/Arabic/Cyrillic/CJK/accents."""
    if not title:
        return None
    t = unicodedata.normalize("NFKC", title).casefold()
    t = _PUNCT_STRIP_RE.sub(" ", t)
    t = _WS_RE.sub(" ", t).strip()
    return t or None


def canonical_author(authors: list | None) -> str | None:
    """Unicode-safe first-author canonical form."""
    if not authors:
        return None
    first = authors[0]
    if isinstance(first, str):
        name = first
    elif isinstance(first, dict):
        name = (
            first.get("name")
            or first.get("family")
            or first.get("last")
            or ""
        )
    else:
        return None
    name = unicodedata.normalize("NFKC", name).casefold()
    name = "".join(c for c in name if c.isalpha() or c.isspace())
    name = _WS_RE.sub(" ", name).strip()
    return name or None


def identity_key_for(
    *,
    doi: str | None,
    title: str | None,
    authors: list | None,
    year: int | None,
) -> str:
    """DOI dominates; else title+first_author+year."""
    cdoi = canonical_doi(doi)
    if cdoi:
        blob = "doi::" + cdoi
    else:
        parts = [
            "tay",
            canonical_title(title) or "",
            canonical_author(authors) or "",
            str(year) if year else "",
        ]
        blob = "::".join(parts)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def claim_hash_for(
    *,
    manuscript_version_id: str,
    section_id: str | None,
    text: str,
) -> str:
    payload = "|".join([
        CLAIM_EXTRACTION_VERSION,
        str(manuscript_version_id),
        str(section_id or ""),
        normalize_text(text).lower(),
    ])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def is_supporting(level: str) -> bool:
    return level in (
        SupportLevel.SUPPORTS.value,
        SupportLevel.PARTIALLY_SUPPORTS.value,
    )


__all__ = [
    "M30_VERSION",
    "CLAIM_EXTRACTION_VERSION",
    "REFERENCE_NORMALIZATION_VERSION",
    "CLAIM_SUPPORT_THRESHOLD",
    "ClaimType",
    "EvidenceType",
    "SupportLevel",
    "CitationRelationType",
    "CitationStyle",
    "CitationRunStatus",
    "ClaimStatus",
    "CLAIM_TYPES",
    "EVIDENCE_TYPES",
    "SUPPORT_LEVELS",
    "CITATION_RELATION_TYPES",
    "CITATION_STYLES",
    "CITATION_RUN_STATUSES",
    "CLAIM_STATUSES",
    "normalize_text",
    "canonical_doi",
    "canonical_title",
    "canonical_author",
    "identity_key_for",
    "claim_hash_for",
    "is_supporting",
]
