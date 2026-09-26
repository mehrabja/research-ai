"""M34 — Manuscript branch (workstream) management."""
from __future__ import annotations

import uuid

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.exceptions import (
    CollaborationConflict,
    CollaborationInvalid,
    CollaborationNotFound,
)
from app.db.models.collaboration import ManuscriptBranch
from app.db.models.manuscript import Manuscript, ManuscriptVersion
from app.db.models.report import Report
from app.services.collaboration import events as events_svc
from app.services.collaboration import permissions as perms


def _project_id_for_manuscript(
    db: Session, *, manuscript_id: uuid.UUID,
) -> uuid.UUID:
    ms = db.get(Manuscript, manuscript_id)
    if ms is None:
        raise CollaborationNotFound()
    report = db.get(Report, ms.report_id)
    if report is None or report.project_id is None:
        raise CollaborationNotFound()
    return report.project_id


def create_branch(
    db: Session,
    *,
    actor_user_id: uuid.UUID,
    manuscript_id: uuid.UUID,
    name: str,
    head_version_id: uuid.UUID,
    is_default: bool = False,
) -> ManuscriptBranch:
    project_id = _project_id_for_manuscript(
        db, manuscript_id=manuscript_id,
    )
    perms.require_write(
        db, project_id=project_id, user_id=actor_user_id,
    )
    if not name:
        raise CollaborationInvalid("branch name is required")
    head = db.get(ManuscriptVersion, head_version_id)
    if head is None or head.manuscript_id != manuscript_id:
        raise CollaborationInvalid(
            "head version does not belong to this manuscript"
        )
    existing = db.execute(
        select(ManuscriptBranch).where(
            ManuscriptBranch.manuscript_id == manuscript_id,
            ManuscriptBranch.name == name,
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise CollaborationConflict("branch name already exists")

    if is_default:
        db.execute(
            update(ManuscriptBranch)
            .where(
                ManuscriptBranch.manuscript_id == manuscript_id,
                ManuscriptBranch.is_default.is_(True),
            )
            .values(is_default=False)
        )
        db.flush()

    branch = ManuscriptBranch(
        manuscript_id=manuscript_id,
        name=name,
        head_version_id=head_version_id,
        is_default=is_default,
        created_by=actor_user_id,
    )
    db.add(branch)
    db.flush()
    events_svc.emit_event(
        db,
        project_id=project_id,
        actor_user_id=actor_user_id,
        event_type="branch_created",
        target_type="manuscript_branch",
        target_id=branch.id,
        metadata={"name": name, "is_default": is_default},
    )
    return branch


def list_branches(
    db: Session,
    *,
    actor_user_id: uuid.UUID,
    manuscript_id: uuid.UUID,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[ManuscriptBranch], int]:
    project_id = _project_id_for_manuscript(
        db, manuscript_id=manuscript_id,
    )
    perms.require_read(
        db, project_id=project_id, user_id=actor_user_id,
    )
    base = select(ManuscriptBranch).where(
        ManuscriptBranch.manuscript_id == manuscript_id
    )
    total = int(db.execute(
        select(func.count()).select_from(base.subquery())
    ).scalar_one())
    rows = list(db.execute(
        base.order_by(
            ManuscriptBranch.is_default.desc(),
            ManuscriptBranch.name.asc(),
            ManuscriptBranch.id.asc(),
        ).limit(limit).offset(offset)
    ).scalars().all())
    return rows, total


def get_branch(
    db: Session, *, actor_user_id: uuid.UUID, branch_id: uuid.UUID,
) -> ManuscriptBranch:
    branch = db.get(ManuscriptBranch, branch_id)
    if branch is None:
        raise CollaborationNotFound()
    project_id = _project_id_for_manuscript(
        db, manuscript_id=branch.manuscript_id,
    )
    perms.require_read(
        db, project_id=project_id, user_id=actor_user_id,
    )
    return branch


def get_default_branch(
    db: Session, *, manuscript_id: uuid.UUID,
) -> ManuscriptBranch | None:
    return db.execute(
        select(ManuscriptBranch).where(
            ManuscriptBranch.manuscript_id == manuscript_id,
            ManuscriptBranch.is_default.is_(True),
        )
    ).scalar_one_or_none()


__all__ = [
    "create_branch",
    "list_branches",
    "get_branch",
    "get_default_branch",
]
