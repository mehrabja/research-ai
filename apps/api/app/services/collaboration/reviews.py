"""M34 — Structured review tasks."""
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
from app.db.models.collaboration import ManuscriptReviewTask
from app.db.models.manuscript import Manuscript, ManuscriptVersion
from app.db.models.report import Report
from app.domain.collaboration import (
    REVIEW_SEVERITIES,
    REVIEW_TASK_STATUSES,
)
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


def create_review_task(
    db: Session,
    *,
    actor_user_id: uuid.UUID,
    manuscript_version_id: uuid.UUID,
    title: str,
    description: str | None = None,
    severity: str = "info",
    assignee_user_id: uuid.UUID | None = None,
    scope: dict | None = None,
    related_section_id: uuid.UUID | None = None,
    related_qa_finding_id: uuid.UUID | None = None,
    related_citation_id: uuid.UUID | None = None,
    due_at: datetime | None = None,
) -> ManuscriptReviewTask:
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
    perms.require_review(
        db, project_id=project_id, user_id=actor_user_id,
    )
    if not title or not title.strip():
        raise CollaborationInvalid("review title is required")
    if severity not in REVIEW_SEVERITIES:
        raise CollaborationInvalid(f"unknown severity: {severity}")

    existing = list(db.execute(
        select(ManuscriptReviewTask).where(
            ManuscriptReviewTask.manuscript_version_id
            == manuscript_version_id
        )
    ).scalars().all())
    if len(existing) >= int(
        settings.collaboration_max_review_tasks_per_version
    ):
        raise CollaborationInvalid("review task limit reached")

    task = ManuscriptReviewTask(
        project_id=project_id,
        report_id=report_id,
        manuscript_version_id=manuscript_version_id,
        assignee_user_id=assignee_user_id,
        created_by_user_id=actor_user_id,
        title=title.strip(),
        description=description,
        scope=scope,
        severity=severity,
        status="open",
        related_section_id=related_section_id,
        related_qa_finding_id=related_qa_finding_id,
        related_citation_id=related_citation_id,
        due_at=due_at,
    )
    db.add(task)
    db.flush()
    events_svc.emit_event(
        db,
        project_id=project_id,
        actor_user_id=actor_user_id,
        event_type="review_task_created",
        target_type="manuscript_review_task",
        target_id=task.id,
        metadata={
            "severity": severity,
            "assignee_user_id": (
                str(assignee_user_id) if assignee_user_id else None
            ),
        },
    )
    return task


def list_review_tasks(
    db: Session,
    *,
    actor_user_id: uuid.UUID,
    manuscript_version_id: uuid.UUID,
    status: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[ManuscriptReviewTask], int]:
    _version, project_id, _rid = _load_chain(
        db,
        actor_user_id=actor_user_id,
        manuscript_version_id=manuscript_version_id,
    )
    perms.require_read(
        db, project_id=project_id, user_id=actor_user_id,
    )
    from sqlalchemy import func

    base = select(ManuscriptReviewTask).where(
        ManuscriptReviewTask.manuscript_version_id
        == manuscript_version_id
    )
    if status:
        base = base.where(ManuscriptReviewTask.status == status)
    total = int(db.execute(
        select(func.count()).select_from(base.subquery())
    ).scalar_one())
    rows = list(db.execute(
        base.order_by(
            ManuscriptReviewTask.created_at.asc(),
            ManuscriptReviewTask.id.asc(),
        ).limit(limit).offset(offset)
    ).scalars().all())
    return rows, total


def change_review_status(
    db: Session,
    *,
    actor_user_id: uuid.UUID,
    review_task_id: uuid.UUID,
    new_status: str,
    resolution: dict | None = None,
) -> ManuscriptReviewTask:
    task = db.get(ManuscriptReviewTask, review_task_id)
    if task is None:
        raise CollaborationNotFound()
    perms.require_review(
        db,
        project_id=task.project_id,
        user_id=actor_user_id,
    )
    if new_status not in REVIEW_TASK_STATUSES:
        raise CollaborationInvalid(
            f"unknown review status: {new_status}"
        )
    old_status = task.status
    task.status = new_status
    if new_status in ("resolved", "rejected"):
        task.resolved_at = datetime.now(UTC)
        task.resolution = resolution or {}
    else:
        task.resolved_at = None
        if resolution is not None:
            task.resolution = resolution
    db.flush()
    events_svc.emit_event(
        db,
        project_id=task.project_id,
        actor_user_id=actor_user_id,
        event_type="review_task_status_changed",
        target_type="manuscript_review_task",
        target_id=task.id,
        metadata={
            "from_status": old_status,
            "to_status": new_status,
        },
    )
    return task


__all__ = [
    "create_review_task",
    "list_review_tasks",
    "change_review_status",
]
