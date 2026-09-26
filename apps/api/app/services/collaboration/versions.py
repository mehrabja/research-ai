"""M34 — Manuscript version graph (parent/child links)."""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import (
    CollaborationInvalid,
    CollaborationNotFound,
)
from app.db.models.collaboration import ManuscriptBranch
from app.db.models.manuscript import (
    Manuscript,
    ManuscriptVersion,
)
from app.domain.collaboration import COLLABORATION_EVENT_TYPES
from app.services.collaboration import events as events_svc
from app.services.collaboration import permissions as perms


def _load_chain(
    db: Session,
    *,
    actor_user_id: uuid.UUID,
    manuscript_version_id: uuid.UUID,
) -> tuple[ManuscriptVersion, Manuscript, uuid.UUID]:
    version = db.get(ManuscriptVersion, manuscript_version_id)
    if version is None:
        raise CollaborationNotFound()
    manuscript = db.get(Manuscript, version.manuscript_id)
    if manuscript is None:
        raise CollaborationNotFound()
    from app.db.models.report import Report

    report = db.get(Report, manuscript.report_id)
    if report is None or report.project_id is None:
        raise CollaborationNotFound()
    project_id = report.project_id
    perms.require_read(
        db, project_id=project_id, user_id=actor_user_id,
    )
    return version, manuscript, project_id


def list_versions(
    db: Session,
    *,
    actor_user_id: uuid.UUID,
    manuscript_id: uuid.UUID,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[ManuscriptVersion], int]:
    manuscript = db.get(Manuscript, manuscript_id)
    if manuscript is None:
        raise CollaborationNotFound()
    from app.db.models.report import Report

    report = db.get(Report, manuscript.report_id)
    if report is None or report.project_id is None:
        raise CollaborationNotFound()
    perms.require_read(
        db, project_id=report.project_id, user_id=actor_user_id,
    )
    from sqlalchemy import func

    base = select(ManuscriptVersion).where(
        ManuscriptVersion.manuscript_id == manuscript_id
    )
    total = int(db.execute(
        select(func.count()).select_from(base.subquery())
    ).scalar_one())
    rows = list(db.execute(
        base.order_by(
            ManuscriptVersion.version.desc(),
            ManuscriptVersion.id.desc(),
        ).limit(limit).offset(offset)
    ).scalars().all())
    return rows, total


def get_version(
    db: Session,
    *,
    actor_user_id: uuid.UUID,
    manuscript_version_id: uuid.UUID,
) -> ManuscriptVersion:
    version, _ms, _pid = _load_chain(
        db,
        actor_user_id=actor_user_id,
        manuscript_version_id=manuscript_version_id,
    )
    return version


def record_version_created(
    db: Session,
    *,
    actor_user_id: uuid.UUID,
    manuscript_version_id: uuid.UUID,
    parent_version_id: uuid.UUID | None,
    reason: str | None,
) -> ManuscriptVersion:
    """Stamp parent_version_id on an existing (draft) version and emit event.

    Cannot be called on a version that already has a parent set to a
    different value.
    """
    version, _ms, project_id = _load_chain(
        db,
        actor_user_id=actor_user_id,
        manuscript_version_id=manuscript_version_id,
    )
    perms.require_write(
        db, project_id=project_id, user_id=actor_user_id,
    )
    if parent_version_id is not None:
        if parent_version_id == manuscript_version_id:
            raise CollaborationInvalid(
                "version cannot be its own parent"
            )
        parent = db.get(ManuscriptVersion, parent_version_id)
        if parent is None or parent.manuscript_id != version.manuscript_id:
            raise CollaborationInvalid(
                "parent version does not belong to this manuscript"
            )
        if (
            version.parent_version_id is not None
            and version.parent_version_id != parent_version_id
        ):
            raise CollaborationInvalid(
                "version already has a different parent"
            )
    version.parent_version_id = parent_version_id
    db.flush()
    events_svc.emit_event(
        db,
        project_id=project_id,
        actor_user_id=actor_user_id,
        event_type="version_created",
        target_type="manuscript_version",
        target_id=version.id,
        metadata={
            "parent_version_id": (
                str(parent_version_id) if parent_version_id else None
            ),
            "reason": reason,
        },
    )
    return version


_ = COLLABORATION_EVENT_TYPES, ManuscriptBranch  # reserved


__all__ = [
    "list_versions",
    "get_version",
    "record_version_created",
]
