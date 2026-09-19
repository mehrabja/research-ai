"""Report service.

Ownership filtering lives inside the SQL query, not only in the route.
This makes ownership part of the data-access boundary and prevents
cross-user access even if a future caller bypasses the HTTP route.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import (
    ProjectNotFound,
    ProjectReportAttachForbiddenError,
    ReportNotFound,
)
from app.db.models.project import Project
from app.db.models.report import Report
from app.domain.project import EDITABLE_PROJECT_STATUSES


def create_report(
    db: Session,
    *,
    user_id: uuid.UUID,
    data: dict[str, Any],
) -> Report:
    project_id = data.get("project_id")
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

    # status is server-controlled. The database server_default remains
    # authoritative and initializes new reports as "draft".
    report = Report(
        user_id=user_id,
        **data,
    )

    try:
        db.add(report)
        db.commit()
        db.refresh(report)
    except Exception:
        db.rollback()
        raise

    return report

def list_reports(
    db: Session,
    *,
    user_id: uuid.UUID,
) -> list[Report]:
    stmt = (
        select(Report)
        .where(
            Report.user_id == user_id,
            Report.deleted_at.is_(None),
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
