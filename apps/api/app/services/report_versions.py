"""Report version service."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import ReportVersionNotFound
from app.db.models.report import Report, ReportVersion
from app.services.report_events import create_version_created_event
from app.services.reports import get_report

_UNIQUE_VIOLATION = "23505"
_MAX_NUMBER_ATTEMPTS = 5


def create_report_version(
    db: Session,
    *,
    user_id: uuid.UUID,
    report_id: uuid.UUID,
    language: str,
    content: str,
    created_by_user: bool = False,
    change_type: str | None = None,
    commit: bool = True,
) -> ReportVersion:
    """Create a new immutable version and its audit event atomically."""
    if not commit:
        report = db.execute(
            select(Report)
            .where(
                Report.id == report_id,
                Report.user_id == user_id,
                Report.deleted_at.is_(None),
            )
            .with_for_update()
        ).scalar_one_or_none()
        if report is None:
            from app.core.exceptions import ReportNotFound
            raise ReportNotFound()

        next_number = (
            db.execute(
                select(
                    func.coalesce(
                        func.max(ReportVersion.version_number),
                        0,
                    )
                    + 1
                ).where(
                    ReportVersion.report_id == report_id,
                    ReportVersion.language == language,
                )
            ).scalar_one()
        )
        version = ReportVersion(
            report_id=report_id,
            version_number=next_number,
            language=language,
            content=content,
            created_by_user=created_by_user,
            change_type=change_type,
        )
        db.add(version)
        db.flush()
        return version

    get_report(
        db,
        user_id=user_id,
        report_id=report_id,
    )

    last_error: IntegrityError | None = None

    for _ in range(_MAX_NUMBER_ATTEMPTS):
        next_number = (
            db.execute(
                select(
                    func.coalesce(
                        func.max(ReportVersion.version_number),
                        0,
                    )
                    + 1
                ).where(
                    ReportVersion.report_id == report_id,
                    ReportVersion.language == language,
                )
            ).scalar_one()
        )

        version = ReportVersion(
            report_id=report_id,
            version_number=next_number,
            language=language,
            content=content,
            created_by_user=created_by_user,
            change_type=change_type,
        )

        try:
            db.add(version)
            db.flush()

            create_version_created_event(
                db,
                report_id=report_id,
                user_id=user_id,
                version_id=version.id,
                metadata={
                    "version_number": version.version_number,
                    "language": version.language,
                },
            )

            db.commit()
            db.refresh(version)
            return version
        except IntegrityError as exc:
            db.rollback()
            sqlstate = getattr(exc.orig, "sqlstate", None)
            if sqlstate != _UNIQUE_VIOLATION:
                raise
            last_error = exc
            continue

    assert last_error is not None
    raise last_error


def get_report_version(
    db: Session,
    *,
    user_id: uuid.UUID,
    report_id: uuid.UUID,
    version_id: uuid.UUID,
) -> ReportVersion:
    get_report(
        db,
        user_id=user_id,
        report_id=report_id,
    )

    version = (
        db.execute(
            select(ReportVersion)
            .where(
                ReportVersion.id == version_id,
                ReportVersion.report_id == report_id,
            )
        )
        .scalar_one_or_none()
    )

    if version is None:
        raise ReportVersionNotFound()

    return version
