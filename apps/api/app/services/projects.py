"""M18-A — Project service."""
from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import ProjectNotFound, QuotaExceeded
from app.db.models.project import Project, ProjectEvent
from app.db.models.report import Report
from app.domain.project import (
    ALL_PROJECT_STATUSES,
    EDITABLE_PROJECT_STATUSES,
    InvalidProjectPayloadError,
    InvalidProjectStatusTransitionError,
    ProjectStatus,
    can_transition,
    normalize_name,
    normalize_optional_text,
    normalize_string_list,
)
from app.services import entitlements as entitlements_service
from app.services import workspaces as workspaces_service
from app.services.audit import emit_audit


def _emit(
    db: Session,
    *,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    event_type: str,
    event_meta: dict[str, Any] | None = None,
) -> None:
    db.add(
        ProjectEvent(
            project_id=project_id,
            user_id=user_id,
            event_type=event_type,
            event_meta=event_meta or {},
        )
    )


def _resolve_workspace(
    db: Session,
    *,
    user_id: uuid.UUID,
    workspace_id: uuid.UUID | None,
):
    if workspace_id is None:
        return workspaces_service.ensure_default_workspace(
            db, user_id=user_id
        )
    workspace, _ = workspaces_service.get_workspace_for_user(
        db,
        workspace_id=workspace_id,
        user_id=user_id,
    )
    return workspace


def create_project(
    db: Session,
    *,
    user_id: uuid.UUID,
    workspace_id: uuid.UUID | None = None,
    name: str,
    description: str | None = None,
    domain: str | None = None,
    research_objective: str | None = None,
    research_questions: Sequence[str] | None = None,
    hypotheses: Sequence[str] | None = None,
    scope: str | None = None,
    constraints: str | None = None,
    status: str = ProjectStatus.DRAFT.value,
    commit: bool = True,
) -> Project:
    if status not in ALL_PROJECT_STATUSES:
        raise InvalidProjectPayloadError(f"unknown status: {status}")
    if status == ProjectStatus.ARCHIVED.value:
        raise InvalidProjectPayloadError("cannot create project as archived")
    workspace = _resolve_workspace(
        db,
        user_id=user_id,
        workspace_id=workspace_id,
    )
    try:
        entitlements_service.check_and_reserve_project_slot(
            db, workspace_id=workspace.id
        )
    except QuotaExceeded as exc:
        emit_audit(
            "QUOTA_DENIED",
            user_id=str(user_id),
            workspace_id=str(workspace.id),
            feature=exc.feature,
            limit=exc.limit,
            current=exc.current,
        )
        raise
    project = Project(
        user_id=user_id,
        workspace_id=workspace.id,
        name=normalize_name(name),
        description=normalize_optional_text(description, field="description"),
        domain=normalize_optional_text(domain, field="domain"),
        research_objective=normalize_optional_text(
            research_objective, field="research_objective"
        ),
        research_questions=normalize_string_list(
            list(research_questions or []), field="research_questions"
        ),
        hypotheses=normalize_string_list(
            list(hypotheses or []), field="hypotheses"
        ),
        scope=normalize_optional_text(scope, field="scope"),
        constraints=normalize_optional_text(constraints, field="constraints"),
        status=status,
    )
    db.add(project)
    db.flush()  # populate project.id
    _emit(
        db,
        project_id=project.id,
        user_id=user_id,
        event_type="project_created",
        event_meta={"status": status},
    )
    if commit:
        db.commit()
        db.refresh(project)
    else:
        db.flush()
    return project


def get_project(
    db: Session,
    *,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
    workspace_id: uuid.UUID | None = None,
) -> Project:
    filters: list[Any] = [
        Project.id == project_id,
        Project.user_id == user_id,
    ]
    if workspace_id is not None:
        filters.append(Project.workspace_id == workspace_id)

    project = db.execute(
        select(Project).where(*filters)
    ).scalar_one_or_none()
    if project is None:
        raise ProjectNotFound()
    workspaces_service.get_workspace_for_user(
        db,
        workspace_id=project.workspace_id,
        user_id=user_id,
    )
    return project


def list_projects(
    db: Session,
    *,
    user_id: uuid.UUID,
    workspace_id: uuid.UUID | None = None,
    status: str | None = None,
    include_archived: bool = True,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[tuple[Project, int]], int]:
    """Returns list of (project, live_report_count) plus total.

    Uses a single correlated subquery — no N+1.
    """
    workspace = _resolve_workspace(
        db,
        user_id=user_id,
        workspace_id=workspace_id,
    )
    filters: list[Any] = [
        Project.user_id == user_id,
        Project.workspace_id == workspace.id,
    ]
    if status is not None:
        filters.append(Project.status == status)
    elif not include_archived:
        filters.append(Project.status != ProjectStatus.ARCHIVED.value)

    total = int(
        db.execute(
            select(func.count()).select_from(Project).where(*filters)
        ).scalar_one()
    )

    report_count = (
        select(func.count(Report.id))
        .where(
            Report.project_id == Project.id,
            Report.deleted_at.is_(None),
        )
        .correlate(Project)
        .scalar_subquery()
    )

    rows = db.execute(
        select(Project, report_count.label("report_count"))
        .where(*filters)
        .order_by(Project.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return [(p, int(c)) for p, c in rows], total


def _apply_status_transition(project: Project, target: str) -> None:
    if target not in ALL_PROJECT_STATUSES:
        raise InvalidProjectPayloadError(f"unknown status: {target}")
    if target == ProjectStatus.ARCHIVED.value:
        raise InvalidProjectStatusTransitionError(
            "use archive_project() to archive"
        )
    if target == project.status:
        return  # idempotent no-op
    if not can_transition(project.status, target):
        raise InvalidProjectStatusTransitionError(
            f"illegal transition {project.status} -> {target}"
        )
    project.status = target


def update_project(
    db: Session,
    *,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
    workspace_id: uuid.UUID | None = None,
    updates: dict[str, Any],
    commit: bool = True,
) -> Project:
    project = get_project(
        db,
        user_id=user_id,
        project_id=project_id,
        workspace_id=workspace_id,
    )
    if project.status == ProjectStatus.ARCHIVED.value:
        raise InvalidProjectStatusTransitionError(
            "archived project cannot be edited"
        )

    changed: list[str] = []

    if "name" in updates and updates["name"] is not None:
        project.name = normalize_name(updates["name"])
        changed.append("name")

    for field in (
        "description",
        "domain",
        "research_objective",
        "scope",
        "constraints",
    ):
        if field in updates:
            project.__setattr__(
                field,
                normalize_optional_text(updates[field], field=field),
            )
            changed.append(field)

    for field in ("research_questions", "hypotheses"):
        if field in updates:
            project.__setattr__(
                field,
                normalize_string_list(updates[field] or [], field=field),
            )
            changed.append(field)

    if "status" in updates and updates["status"] is not None:
        _apply_status_transition(project, updates["status"])
        changed.append("status")

    if changed:
        _emit(
            db,
            project_id=project.id,
            user_id=user_id,
            event_type="project_updated",
            event_meta={"fields": sorted(changed)},
        )

    if commit:
        db.commit()
        db.refresh(project)
    else:
        db.flush()
    return project


def archive_project(
    db: Session,
    *,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
    workspace_id: uuid.UUID | None = None,
    commit: bool = True,
) -> Project:
    project = get_project(
        db,
        user_id=user_id,
        project_id=project_id,
        workspace_id=workspace_id,
    )
    if project.status == ProjectStatus.ARCHIVED.value:
        return project  # idempotent — no duplicate event
    previous = project.status
    project.status = ProjectStatus.ARCHIVED.value
    project.archived_at = datetime.now(UTC)
    _emit(
        db,
        project_id=project.id,
        user_id=user_id,
        event_type="project_archived",
        event_meta={"from_status": previous},
    )
    if commit:
        db.commit()
        db.refresh(project)
    else:
        db.flush()
    return project


def can_attach_report(project: Project) -> bool:
    return project.status in EDITABLE_PROJECT_STATUSES


def count_project_reports(
    db: Session, *, user_id: uuid.UUID, project_id: uuid.UUID
) -> int:
    return int(
        db.execute(
            select(func.count())
            .select_from(Report)
            .where(
                Report.project_id == project_id,
                Report.user_id == user_id,
                Report.deleted_at.is_(None),
            )
        ).scalar_one()
    )


def list_project_reports(
    db: Session,
    *,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
    workspace_id: uuid.UUID | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Report], int]:
    # Ownership enforced at service boundary.
    get_project(
        db,
        user_id=user_id,
        project_id=project_id,
        workspace_id=workspace_id,
    )

    base = select(Report).where(
        Report.project_id == project_id,
        Report.user_id == user_id,
        Report.deleted_at.is_(None),
    )
    total = int(
        db.execute(
            select(func.count()).select_from(base.subquery())
        ).scalar_one()
    )
    rows = (
        db.execute(
            base.order_by(Report.updated_at.desc()).limit(limit).offset(offset)
        )
        .scalars()
        .all()
    )
    return list(rows), total


def build_project_payload(
    db: Session, *, user_id: uuid.UUID, project: Project
) -> dict[str, Any]:
    return {
        "workspace_id": project.workspace_id,
        "id": project.id,
        "name": project.name,
        "description": project.description,
        "domain": project.domain,
        "research_objective": project.research_objective,
        "research_questions": list(project.research_questions or []),
        "hypotheses": list(project.hypotheses or []),
        "scope": project.scope,
        "constraints": project.constraints,
        "status": project.status,
        "report_count": count_project_reports(
            db, user_id=user_id, project_id=project.id
        ),
        "created_at": project.created_at,
        "updated_at": project.updated_at,
        "archived_at": project.archived_at,
    }
