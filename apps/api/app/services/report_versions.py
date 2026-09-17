"""Report version service."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import ReportVersionNotFound
from app.db.models.report import ReportVersion
from app.services.report_events import create_version_created_event
from app.services.reports import get_report

# PostgreSQL SQLSTATE for unique_violation.
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
) -> ReportVersion:
    """Create a new immutable version and its audit event atomically.

    Version numbering is per ``(report_id, language)`` and is
    computed as ``MAX+1``. The unique constraint
    ``ux_report_versions_report_version_lang`` is the final
    correctness guard. On a 23505 race we retry with a fresh ORM
    object — a rolled-back SQLAlchemy instance must not be reused.

    The version row and its ``version_created`` audit event are
    committed in a single transaction.
    """
    # Ownership check (also enforces non-deleted + owned).
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

        # Fresh ORM object every attempt — required because a
        # rollback detaches the previous instance.
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
            # Flush so that version.id (server-generated UUID) exists
            # before we reference it in the audit event.
            db.flush()

            # Same transaction: audit event is added but NOT committed.
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

            # Single commit for both the version and its audit event.
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
