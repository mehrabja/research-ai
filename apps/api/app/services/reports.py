"""Report service.

Ownership filtering lives inside the SQL query, not only in the route.
This makes ownership part of the data-access boundary and prevents
cross-user access even if a future caller bypasses the HTTP route.

M37:
  * ``create_report`` enforces ``reports.monthly`` (Phase 2-G) and
    emits a ``reports_created`` usage event (Phase 2-A3) in the same
    transaction.
"""
from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

logger = logging.getLogger(__name__)


from app.core.exceptions import (
    ProjectNotFound,
    ProjectReportAttachForbiddenError,
    QuotaExceeded,
    ReportNotFound,
)
from app.db.models.project import Project
from app.db.models.report import Report
from app.domain.project import EDITABLE_PROJECT_STATUSES
from app.services import entitlements as entitlements_service
from app.services import usage as usage_service
from app.services import workspaces as workspaces_service
from app.services.audit import emit_audit


def create_report(
    db: Session,
    *,
    user_id: uuid.UUID,
    data: dict[str, Any],
    workspace_id: uuid.UUID | None = None,
) -> Report:
    project_id = data.get("project_id")
    requested_workspace_id = workspace_id
    project: Project | None = None
    if project_id is not None:
        project = db.execute(
            select(Project).where(
                Project.id == project_id,
                Project.user_id == user_id,
            )
        ).scalar_one_or_none()
        if project is None:
            # Same 404 for missing and foreign projects (no oracle).
            raise ProjectNotFound()
        if project.status not in EDITABLE_PROJECT_STATUSES:
            raise ProjectReportAttachForbiddenError()
        if (
            requested_workspace_id is not None
            and project.workspace_id != requested_workspace_id
        ):
            raise ProjectNotFound()

    # Resolve workspace BEFORE quota check.
    if project is not None:
        effective_workspace_id = project.workspace_id
    else:
        workspace = (
            workspaces_service.get_workspace_for_user(
                db,
                workspace_id=requested_workspace_id,
                user_id=user_id,
            )[0]
            if requested_workspace_id is not None
            else workspaces_service.ensure_default_workspace(
                db, user_id=user_id
            )
        )
        default_workspace = workspaces_service.ensure_default_workspace(
            db, user_id=user_id
        )
        if workspace.id != default_workspace.id:
            raise ProjectNotFound(
                "A report without a project must use the default workspace."
            )
        effective_workspace_id = workspace.id

    workspaces_service.get_workspace_for_user(
        db,
        workspace_id=effective_workspace_id,
        user_id=user_id,
    )

    # Monthly quota check (M37 Phase 2-G).
    try:
        entitlements_service.check_and_reserve_reports_monthly_slot(
            db, workspace_id=effective_workspace_id
        )
    except QuotaExceeded as exc:
        emit_audit(
            "QUOTA_DENIED",
            user_id=str(user_id),
            workspace_id=str(effective_workspace_id),
            feature=exc.feature,
            limit=exc.limit,
            current=exc.current,
        )
        raise

    # status is server-controlled. The database server_default remains
    # authoritative and initializes new reports as "draft".
    report = Report(
        user_id=user_id,
        **data,
    )

    try:
        db.add(report)
        db.flush()  # populate report.id

        usage_service.record_event(
            db,
            workspace_id=effective_workspace_id,
            user_id=user_id,
            metric="reports_created",
            quantity=1,
            idempotency_key=usage_service.report_created_key(
                report.id
            ),
            source_type="report",
            source_id=report.id,
        )

        db.commit()
        db.refresh(report)
    except Exception:
        db.rollback()
        raise

    if report.project_id is not None:
        try:
            from app.services.artifact_evidence import (
                sync_ready_project_files_for_report,
            )

            sync_ready_project_files_for_report(
                db,
                project_id=report.project_id,
                report_id=report.id,
                user_id=user_id,
            )
        except Exception:  # noqa: BLE001
            logger.exception(
                "artifact evidence sync on report creation failed "
                "report_id=%s",
                report.id,
            )

    return report


def list_reports(
    db: Session,
    *,
    user_id: uuid.UUID,
    workspace_id: uuid.UUID | None = None,
) -> list[Report]:
    default_workspace = workspaces_service.ensure_default_workspace(
        db, user_id=user_id
    )
    workspace = (
        workspaces_service.get_workspace_for_user(
            db,
            workspace_id=workspace_id,
            user_id=user_id,
        )[0]
        if workspace_id is not None
        else default_workspace
    )

    workspace_filter: ColumnElement[bool]
    if workspace.id == default_workspace.id:
        workspace_filter = (
            (Project.workspace_id == workspace.id)
            | (Report.project_id.is_(None))
        )
    else:
        workspace_filter = Project.workspace_id == workspace.id

    stmt = (
        select(Report)
        .outerjoin(Project, Project.id == Report.project_id)
        .where(
            Report.user_id == user_id,
            Report.deleted_at.is_(None),
            workspace_filter,
        )
        .order_by(
            Report.updated_at.desc(),
            Report.created_at.desc(),
            Report.id.asc(),
        )
    )

    return list(
        db.execute(stmt).scalars().all()
    )


def get_report(
    db: Session,
    *,
    user_id: uuid.UUID,
    report_id: uuid.UUID,
) -> Report:
    stmt = select(Report).where(
        Report.id == report_id,
        Report.user_id == user_id,
        Report.deleted_at.is_(None),
    )

    report = db.execute(stmt).scalar_one_or_none()

    if report is None:
        # Same response for missing, foreign, and soft-deleted reports.
        raise ReportNotFound()

    if report.project_id is None:
        effective_workspace_id = (
            workspaces_service.ensure_default_workspace(
                db, user_id=report.user_id
            ).id
        )
    else:
        project = db.get(Project, report.project_id)
        if project is None:
            raise ReportNotFound()
        effective_workspace_id = project.workspace_id

    workspaces_service.get_workspace_for_user(
        db,
        workspace_id=effective_workspace_id,
        user_id=user_id,
    )
    return report


def update_report(
    db: Session,
    *,
    user_id: uuid.UUID,
    report_id: uuid.UUID,
    changes: dict[str, Any],
) -> Report:
    report = get_report(
        db,
        user_id=user_id,
        report_id=report_id,
    )

    for key, value in changes.items():
        setattr(report, key, value)

    try:
        db.commit()
        db.refresh(report)
    except Exception:
        db.rollback()
        raise

    return report


def soft_delete_report(
    db: Session,
    *,
    user_id: uuid.UUID,
    report_id: uuid.UUID,
) -> None:
    report = get_report(
        db,
        user_id=user_id,
        report_id=report_id,
    )

    # Soft delete uses deleted_at only. status remains unchanged.
    report.deleted_at = datetime.now(UTC)

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise


__all__ = [
    "create_report",
    "get_report",
    "list_reports",
    "soft_delete_report",
    "update_report",
]
