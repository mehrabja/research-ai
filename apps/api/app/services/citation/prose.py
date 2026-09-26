"""M28.5 — Manuscript prose adapter.

Read boundary only. Fetches structured prose from M28.5 tables and
returns a ManuscriptProse dataclass consumed by M30 / M32.

Returns None when prose genuinely does not exist. NEVER synthesizes
prose from section metadata (title/purpose/research_contract).
"""
from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.manuscript_prose import (
    ManuscriptProseRun,
    ManuscriptProseSection,
)
from app.domain.citation import normalize_text
from app.domain.manuscript_prose import ProseRunStatus


@dataclass(frozen=True)
class ManuscriptSectionProse:
    section_id: uuid.UUID
    section_key: str
    section_type: str
    display_order: int
    title: str
    text: str
    char_start: int
    char_end: int


@dataclass(frozen=True)
class ManuscriptProse:
    manuscript_version_id: uuid.UUID
    content_hash: str
    sections: tuple[ManuscriptSectionProse, ...]

    @property
    def full_text(self) -> str:
        return "\n\n".join(s.text for s in self.sections)

    @property
    def is_empty(self) -> bool:
        return not self.sections


def get_manuscript_prose(
    db: Session, *, manuscript_version_id: uuid.UUID,
) -> ManuscriptProse | None:
    """Return canonical manuscript prose, or None.

    Looks up the latest completed M28.5 run for the given base
    manuscript version and returns its sections in display order.
    """
    run = db.execute(
        select(ManuscriptProseRun)
        .where(
            ManuscriptProseRun.base_manuscript_version_id
            == manuscript_version_id,
            ManuscriptProseRun.status == ProseRunStatus.COMPLETED.value,
        )
        .order_by(
            ManuscriptProseRun.created_at.desc(),
            ManuscriptProseRun.id.desc(),
        )
        .limit(1)
    ).scalar_one_or_none()
    if run is None:
        return None

    section_rows = list(db.execute(
        select(ManuscriptProseSection)
        .where(ManuscriptProseSection.run_id == run.id)
        .order_by(ManuscriptProseSection.display_order.asc())
    ).scalars().all())
    if not section_rows:
        return None

    sections: list[ManuscriptSectionProse] = []
    normalized_chunks: list[str] = []
    cursor = 0
    for s in section_rows:
        body = (s.text or "").strip()
        if not body:
            continue
        norm = normalize_text(body)
        if not norm:
            continue
        start = cursor
        end = start + len(norm)
        cursor = end + 2
        normalized_chunks.append(norm)
        sections.append(ManuscriptSectionProse(
            section_id=s.manuscript_section_id or s.id,
            section_key=s.section_key,
            section_type=s.section_type,
            display_order=s.display_order,
            title=s.title,
            text=norm,
            char_start=start,
            char_end=end,
        ))

    if not sections:
        return None

    full = "\n\n".join(normalized_chunks)
    content_hash = hashlib.sha256(full.encode("utf-8")).hexdigest()
    return ManuscriptProse(
        manuscript_version_id=manuscript_version_id,
        content_hash=content_hash,
        sections=tuple(sections),
    )


def build_manuscript_prose_from_section_texts(
    db: Session,
    *,
    manuscript_version_id: uuid.UUID,
    section_texts: dict[uuid.UUID, str],
) -> ManuscriptProse | None:
    """Legacy helper retained for tests/backwards compatibility."""
    sections: list[ManuscriptSectionProse] = []
    normalized_chunks: list[str] = []
    cursor = 0
    for sid, raw in section_texts.items():
        norm = normalize_text((raw or "").strip())
        if not norm:
            continue
        start = cursor
        end = start + len(norm)
        cursor = end + 2
        normalized_chunks.append(norm)
        sections.append(ManuscriptSectionProse(
            section_id=sid,
            section_key=str(sid),
            section_type="custom",
            display_order=0,
            title="",
            text=norm,
            char_start=start,
            char_end=end,
        ))
    if not sections:
        return None
    full = "\n\n".join(normalized_chunks)
    content_hash = hashlib.sha256(full.encode("utf-8")).hexdigest()
    return ManuscriptProse(
        manuscript_version_id=manuscript_version_id,
        content_hash=content_hash,
        sections=tuple(sections),
    )


__all__ = [
    "ManuscriptProse",
    "ManuscriptSectionProse",
    "get_manuscript_prose",
    "build_manuscript_prose_from_section_texts",
]
