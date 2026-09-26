"""M28.5 — Deterministic post-generation validation."""
from __future__ import annotations

from dataclasses import dataclass, field

from app.services.manuscript_prose.serialization import SectionUnit


@dataclass
class ValidationOutcome:
    status: str
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


_FORBIDDEN_FRAGMENTS = (
    "as an ai language model",
    "as an ai, i cannot",
    "i cannot provide",
    "[insert ",
    "{{",
    "}}",
    "lorem ipsum",
)


def validate_section(
    unit: SectionUnit,
    *,
    known_evidence_ids: set[str],
    known_citation_ids: set[str],
    max_words: int,
) -> ValidationOutcome:
    errors: list[str] = []
    warnings: list[str] = []

    if unit.word_count > max_words:
        errors.append(
            f"section_word_budget_exceeded:"
            f"{unit.word_count}>{max_words}"
        )

    seen_paragraph_ordinals: set[int] = set()
    seen_global_sent_ordinals: set[int] = set()
    for p in unit.paragraphs:
        if p.ordinal in seen_paragraph_ordinals:
            errors.append(f"duplicate_paragraph_ordinal:{p.ordinal}")
        seen_paragraph_ordinals.add(p.ordinal)

        if not p.sentences:
            warnings.append(
                f"empty_paragraph:{unit.section_key}:{p.ordinal}"
            )
        for s in p.sentences:
            lowered = s.text.lower()
            for frag in _FORBIDDEN_FRAGMENTS:
                if frag in lowered:
                    errors.append(
                        f"forbidden_fragment:{unit.section_key}:"
                        f"{frag}"
                    )
            for ref in s.evidence_refs or []:
                if ref and ref not in known_evidence_ids:
                    errors.append(
                        f"unknown_evidence_ref:{unit.section_key}:{ref}"
                    )
            for ref in s.citation_refs or []:
                if ref and ref not in known_citation_ids:
                    errors.append(
                        f"unknown_citation_ref:{unit.section_key}:{ref}"
                    )
        _ = seen_global_sent_ordinals  # reserved for future ordering

    return ValidationOutcome(
        status="valid" if not errors else "invalid",
        errors=errors,
        warnings=warnings,
    )


__all__ = ["ValidationOutcome", "validate_section"]
