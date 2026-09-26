"""M34 — Branch merge semantics.

Merging is represented as: create a new version with parent = branch A's
head, then advance the target branch to point at the new version. The
source and target branches keep their original histories unchanged.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
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


def _load_branch(
    db: Session, *, branch_id: uuid.UUID,
) -> tuple[ManuscriptBranch, uuid.UUID]:
    branch = db.get(ManuscriptBranch, branch_id)
    if branch is None:
        raise CollaborationNotFound()
    ms = db.get(Manuscript, branch.manuscript_id)
    if ms is None:
        raise CollaborationNotFound()
    report = db.get(Report, ms.report_id)
    if report is None or report.project_id is None:
        raise CollaborationNotFound()
    return branch, report.project_id


def merge_branches(
    db: Session,
    *,
    actor_user_id: uuid.UUID,
    source_branch_id: uuid.UUID,
    target_branch_id: uuid.UUID,
    new_version_id: uuid.UUID,
    note: str | None = None,
) -> ManuscriptBranch:
    """Record a merge.

    The caller is expected to have already created ``new_version_id``
    (a draft manuscript version) as the merge result and to have set
    its ``parent_version_id`` to the source branch head.
    This function only:
      - validates
      - advances the target branch head
      - emits an audit event
    """
    source, pid_a = _load_branch(db, branch_id=source_branch_id)
    target, pid_b = _load_branch(db, branch_id=target_branch_id)
    if pid_a != pid_b:
        raise CollaborationInvalid("branches belong to different projects")
    if source.manuscript_id != target.manuscript_id:
        raise CollaborationInvalid(
            "branches belong to different manuscripts"
        )
    if source.id == target.id:
        raise CollaborationConflict("cannot merge a branch into itself")

    perms.require_write(
        db, project_id=pid_a, user_id=actor_user_id,
    )

    new_version = db.get(ManuscriptVersion, new_version_id)
    if new_version is None:
        raise CollaborationInvalid("new version not found")
    if new_version.manuscript_id != source.manuscript_id:
        raise CollaborationInvalid(
            "new version belongs to a different manuscript"
        )

    # Deterministic parent rule: parent = source head.
    if new_version.parent_version_id not in (
        None, source.head_version_id,
    ):
        raise CollaborationInvalid(
            "new version's parent does not match source branch head"
        )
    new_version.parent_version_id = source.head_version_id

    target.head_version_id = new_version_id
    db.flush()
    events_svc.emit_event(
        db,
        project_id=pid_a,
        actor_user_id=actor_user_id,
        event_type="branch_merged",
        target_type="manuscript_branch",
        target_id=target.id,
        metadata={
            "source_branch_id": str(source.id),
            "target_branch_id": str(target.id),
            "new_version_id": str(new_version_id),
            "note": note,
        },
    )
    return target


_ = select  # reserved


__all__ = ["merge_branches"]
