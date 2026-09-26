"""M30 — Deterministic claim extraction from real manuscript prose.

When prose is unavailable, returns [] — NEVER falls back to section
metadata (title/purpose) or any structural field.
"""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass

from app.db.models.manuscript import ManuscriptSection
from app.domain.citation import (
    ClaimType,
    claim_hash_for,
)

# Sentence splitting: deterministic, bounded.
# Terminators: . ! ? and equivalent Persian/Arabic punctuation.
_SENT_TERMINATORS = "\\.!?؟۔"
_SENT_SPLIT_RE = re.compile(
    rf"(?<=[{_SENT_TERMINATORS}])\s+",
    re.UNICODE,
)
_MIN_CLAIM_CHARS = 20
_MAX_CLAIM_CHARS = 2000


_SECTION_TYPE_TO_CLAIM: dict[str, str] = {
    "introduction": ClaimType.BACKGROUND.value,
    "background": ClaimType.BACKGROUND.value,
    "related_work": ClaimType.BACKGROUND.value,
    "methods": ClaimType.METHOD.value,
    "methodology": ClaimType.METHOD.value,
    "results": ClaimType.RESULT.value,
    "discussion": ClaimType.SYNTHESIS.value,
    "limitations": ClaimType.LIMITATION.value,
    "conclusion": ClaimType.CONCLUSION.value,
    "future_work": ClaimType.SYNTHESIS.value,
    "appendix": ClaimType.TECHNICAL.value,
}


@dataclass
class ExtractedClaim:
    manuscript_version_id: uuid.UUID
    manuscript_section_id: uuid.UUID | None
    claim_hash: str
    claim_text: str
    claim_type: str
    location: dict | None


def _claim_type_for(section_type: str) -> str:
    return _SECTION_TYPE_TO_CLAIM.get(
        section_type, ClaimType.TECHNICAL.value,
    )


def _split_sentences(text: str) -> list[str]:
    if not text:
        return []
    parts = _SENT_SPLIT_RE.split(text)
    out: list[str] = []
    for p in parts:
        s = p.strip()
        if not s:
            continue
        if len(s) < _MIN_CLAIM_CHARS:
            continue
        if len(s) > _MAX_CLAIM_CHARS:
            s = s[:_MAX_CLAIM_CHARS]
        out.append(s)
    return out


def extract_claims(
    db, *, manuscript_version_id: uuid.UUID,
) -> list[ExtractedClaim]:
    from app.services.citation import prose as prose_svc

    prose = prose_svc.get_manuscript_prose(
        db, manuscript_version_id=manuscript_version_id,
    )
    if prose is None or prose.is_empty:
        return []

    # Ensure sections exist in DB (defensive; prose loader should own this)
    section_ids = [s.section_id for s in prose.sections]
    db_sections = {
        s.id: s
        for s in db.query(ManuscriptSection)
        .filter(ManuscriptSection.id.in_(section_ids))
        .all()
    } if section_ids else {}

    claims: list[ExtractedClaim] = []
    seen: set[str] = set()

    for sec in prose.sections:
        sentences = _split_sentences(sec.text)
        for idx, sentence in enumerate(sentences):
            h = claim_hash_for(
                manuscript_version_id=str(manuscript_version_id),
                section_id=str(sec.section_id),
                text=sentence,
            )
            if h in seen:
                continue
            seen.add(h)

            sec_row = db_sections.get(sec.section_id)
            section_type = sec.section_type or (
                sec_row.section_type if sec_row else ""
            )
            claims.append(ExtractedClaim(
                manuscript_version_id=manuscript_version_id,
                manuscript_section_id=sec.section_id,
                claim_hash=h,
                claim_text=sentence,
                claim_type=_claim_type_for(section_type),
                location={
                    "section_key": sec.section_key,
                    "display_order": sec.display_order,
                    "sentence_index": idx,
                    "char_start": sec.char_start,
                    "char_end": sec.char_end,
                },
            ))

    return claims


__all__ = ["ExtractedClaim", "extract_claims"]
