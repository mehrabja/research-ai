"""M23 — Project literature corpus.

Aggregates Sources (which belong to Reports) into project-level
literature items. Never duplicates Source.

IMPORTANT: this module does NOT commit. The caller (pipeline) owns
the transaction so stages stay atomic.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models.literature import ProjectLiteratureItem
from app.db.models.report import Report
from app.db.models.source import Source
from app.services.projects import get_project

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CorpusSyncResult:
    project_id: uuid.UUID
    total_items: int
    created: int
    preserved_manual: int
    orphaned_source_ids: list[uuid.UUID]


def _existing_item_source_ids(
    db: Session, *, project_id: uuid.UUID
) -> set[uuid.UUID]:
    return set(
        db.execute(
            select(ProjectLiteratureItem.source_id).where(
                ProjectLiteratureItem.project_id == project_id
            )
        ).scalars().all()
    )


def _project_source_ids(
    db: Session, *, project_id: uuid.UUID
) -> list[uuid.UUID]:
    report_ids = list(
        db.execute(
            select(Report.id).where(
                Report.project_id == project_id,
                Report.deleted_at.is_(None),
            )
        ).scalars().all()
    )
    if not report_ids:
        return []
    return list(
        db.execute(
            select(Source.id).where(Source.report_id.in_(report_ids))
        ).scalars().all()
    )


def sync_project_literature_corpus(
    db: Session,
    *,
    user_id: uuid.UUID | None,
    project_id: uuid.UUID,
) -> CorpusSyncResult:

    """Ensure a ProjectLiteratureItem exists for every project source.

    * never duplicates Source
    * never clobbers a manual override
    * does NOT commit — caller owns transaction
    """
    if user_id is None:
        raise ValueError(
            "sync_project_literature_corpus requires user_id"
        )
    get_project(db, user_id=user_id, project_id=project_id)
    source_ids = _project_source_ids(db, project_id=project_id)
    existing = _existing_item_source_ids(db, project_id=project_id)

    created = 0
    preserved = 0

    for sid in source_ids:
        if sid in existing:
            preserved += 1
            continue
        item = ProjectLiteratureItem(
            project_id=project_id,
            source_id=sid,
            screening_status="discovered",
        )
        db.add(item)
        try:
            db.flush()
            created += 1
        except IntegrityError:
            # savepoint to keep session usable
            db.rollback()
            logger.info(
                "corpus_sync_race project_id=%s source_id=%s",
                project_id, sid,
            )

    all_items = list(
        db.execute(
            select(ProjectLiteratureItem).where(
                ProjectLiteratureItem.project_id == project_id
            )
        ).scalars().all()
    )
    live_sources = set(source_ids)
    orphans = [
        it.source_id for it in all_items if it.source_id not in live_sources
    ]

    return CorpusSyncResult(
        project_id=project_id,
        total_items=len(all_items),
        created=created,
        preserved_manual=preserved,
        orphaned_source_ids=orphans,
    )


def get_literature_item_for_project(
    db: Session,
    *,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
    item_id: uuid.UUID,
) -> ProjectLiteratureItem:
    get_project(db, user_id=user_id, project_id=project_id)
    item = db.execute(
        select(ProjectLiteratureItem).where(
            ProjectLiteratureItem.id == item_id,
            ProjectLiteratureItem.project_id == project_id,
        )
    ).scalar_one_or_none()
    if item is None:
        from app.core.exceptions import AppError

        raise AppError("literature item not found", code="not_found")
    return item


def get_sources_for_items(
    db: Session, *, items: list[ProjectLiteratureItem]
) -> dict[uuid.UUID, Source]:
    if not items:
        return {}
    ids = [it.source_id for it in items]
    rows = db.execute(
        select(Source).where(Source.id.in_(ids))
    ).scalars().all()
    return {s.id: s for s in rows}


__all__ = [
    "CorpusSyncResult",
    "get_literature_item_for_project",
    "get_sources_for_items",
    "sync_project_literature_corpus",
]
