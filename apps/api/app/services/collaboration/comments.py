"""M34 — Version-aware comments."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import (
    CollaborationConfigurationInvalid,
    CollaborationInvalid,
    CollaborationNotFound,
)
from app.db.models.collaboration import ManuscriptComment
from app.db.models.manuscript import (
    Manuscript,
    ManuscriptSection,
    ManuscriptVersion,
)
from app.db.models.report import Report
from app.services.collaboration import events as events_svc
from app.services.collaboration import permissions as perms


def _load_chain(
    db: Session,
    *,
    actor_user_id: uuid.UUID,
    manuscript_version_id: uuid.UUID,
) -> tuple[ManuscriptVersion, uuid.UUID, uuid.UUID]:
    version = db.get(ManuscriptVersion, manuscript_version_id)
    if version is None:
        raise CollaborationNotFound()
    ms = db.get(Manuscript, version.manuscript_id)
    if ms is None:
        raise CollaborationNotFound()
    report = db.get(Report, ms.report_id)
    if report is None or report.project_id is None:
        raise CollaborationNotFound()
    return version, report.project_id, report.id


def create_comment(
    db: Session,
    *,
    actor_user_id: uuid.UUID,
    manuscript_version_id: uuid.UUID,
    body: str,
    manuscript_section_id: uuid.UUID | None = None,
    parent_comment_id: uuid.UUID | None = None,
    anchor: dict | None = None,
) -> ManuscriptComment:
    settings = get_settings()
    if not settings.collaboration_enabled:
        raise CollaborationConfigurationInvalid(
            "collaboration is disabled"
        )
    _version, project_id, report_id = _load_chain(
        db,
        actor_user_id=actor_user_id,
        manuscript_version_id=manuscript_version_id,
    )
    perms.require_comment(
        db, project_id=project_id, user_id=actor_user_id,
    )
    if not body or not body.strip():
        raise CollaborationInvalid("comment body is required")

    if manuscript_section_id is not None:
        section = db.get(ManuscriptSection, manuscript_section_id)
        if (
            section is None
            or section.manuscript_version_id != manuscript_version_id
        ):
            raise CollaborationInvalid(
                "section does not belong to this version"
            )

    if parent_comment_id is not None:
        parent = db.get(ManuscriptComment, parent_comment_id)
        if (
            parent is None
            or parent.manuscript_version_id != manuscript_version_id
        ):
            raise CollaborationInvalid(
                "parent comment is not in this version"
            )

    existing = list(db.execute(
        select(ManuscriptComment).where(
            ManuscriptComment.manuscript_version_id
            == manuscript_version_id
        )
    ).scalars().all())
    if len(existing) >= int(
        settings.collaboration_max_comments_per_version
    ):
        raise CollaborationInvalid("comment limit reached")

    comment = ManuscriptComment(
        project_id=project_id,
        report_id=report_id,
        manuscript_version_id=manuscript_version_id,
        manuscript_section_id=manuscript_section_id,
        parent_comment_id=parent_comment_id,
        author_user_id=actor_user_id,
        body=body.strip(),
        status="open",
        anchor=anchor,
    )
    db.add(comment)
    db.flush()
    events_svc.emit_event(
        db,
        project_id=project_id,
        actor_user_id=actor_user_id,
        event_type="comment_created",
        target_type="manuscript_comment",
        target_id=comment.id,
        metadata={
            "manuscript_version_id": str(manuscript_version_id),
            "parent_comment_id": (
                str(parent_comment_id) if parent_comment_id else None
            ),
        },
    )
    return comment


def list_comments(
    db: Session,
    *,
    actor_user_id: uuid.UUID,
    manuscript_version_id: uuid.UUID,
    status: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[ManuscriptComment], int]:
    _version, project_id, _rid = _load_chain(
        db,
        actor_user_id=actor_user_id,
        manuscript_version_id=manuscript_version_id,
    )
    perms.require_read(
        db, project_id=project_id, user_id=actor_user_id,
    )
    from sqlalchemy import func

    base = select(ManuscriptComment).where(
        ManuscriptComment.manuscript_version_id
        == manuscript_version_id
    )
    if status:
        base = base.where(ManuscriptComment.status == status)
    total = int(db.execute(
        select(func.count()).select_from(base.subquery())
    ).scalar_one())
    rows = list(db.execute(
        base.order_by(
            ManuscriptComment.created_at.asc(),
            ManuscriptComment.id.asc(),
        ).limit(limit).offset(offset)
    ).scalars().all())
    return rows, total


def resolve_comment(
    db: Session,
    *,
    actor_user_id: uuid.UUID,
    comment_id: uuid.UUID,
) -> ManuscriptComment:
    comment = db.get(ManuscriptComment, comment_id)
    if comment is None:
        raise CollaborationNotFound()
    perms.require_comment(
        db,
        project_id=comment.project_id,
        user_id=actor_user_id,
    )
    if comment.status == "resolved":
        raise CollaborationInvalid("comment already resolved")
    comment.status = "resolved"
    comment.resolved_by = actor_user_id
    comment.resolved_at = datetime.now(UTC)
    db.flush()
    events_svc.emit_event(
        db,
        project_id=comment.project_id,
        actor_user_id=actor_user_id,
        event_type="comment_resolved",
        target_type="manuscript_comment",
        target_id=comment.id,
    )
    return comment


def reopen_comment(
    db: Session,
    *,
    actor_user_id: uuid.UUID,
    comment_id: uuid.UUID,
) -> ManuscriptComment:
    comment = db.get(ManuscriptComment, comment_id)
    if comment is None:
        raise CollaborationNotFound()
    perms.require_comment(
        db,
        project_id=comment.project_id,
        user_id=actor_user_id,
    )
    if comment.status != "resolved":
        raise CollaborationInvalid("comment is not resolved")
    comment.status = "reopened"
    comment.resolved_by = None
    comment.resolved_at = None
    db.flush()
    events_svc.emit_event(
        db,
        project_id=comment.project_id,
        actor_user_id=actor_user_id,
        event_type="comment_reopened",
        target_type="manuscript_comment",
        target_id=comment.id,
    )
    return comment


__all__ = [
    "create_comment",
    "list_comments",
    "resolve_comment",
    "reopen_comment",
]
