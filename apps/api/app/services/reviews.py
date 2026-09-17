"""M15 — Pre-translation human review service."""
from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.db.models.report import Report, ReportVersion, ReviewEvent
from app.services.report_status import update_report_status
from app.services.report_versions import create_report_version
from app.services.reports import get_report

logger = logging.getLogger(__name__)

REVIEW_STAGE_PRE_TRANSLATION = "pre_translation"
REVIEW_ACTION_EDITED = "edited"
REVIEW_ACTION_APPROVED = "approved"
REVIEW_ACTION_REQUESTED_CHANGES = "requested_changes"
REVIEW_ACTION_REJECTED = "rejected"

MAX_NOTES_LENGTH = 2_000
MAX_CONTENT_LENGTH = 500_000


class StaleReviewVersionError(AppError):
    code = "STALE_REVIEW_VERSION"
    status_code = 409
    message = "The reviewed version is no longer the active review target."


class InvalidReviewStateError(AppError):
    code = "INVALID_REVIEW_STATE"
    status_code = 409
    message = "Report is not in a reviewable state."


class ReviewNotFoundError(AppError):
    code = "REVIEW_NOT_FOUND"
    status_code = 404
    message = "Review context not found."


class ReviewValidationError(AppError):
    code = "REVIEW_VALIDATION_ERROR"
    status_code = 422
    message = "Review input is invalid."


def _resolve_latest_review_version(
    db: Session, *, report_id: uuid.UUID
) -> ReportVersion | None:
    return db.execute(
        select(ReportVersion)
        .where(
            ReportVersion.report_id == report_id,
            ReportVersion.change_type.in_(("humanized", "human_review_edit")),
        )
        .order_by(ReportVersion.version_number.desc())
        .limit(1)
    ).scalar_one_or_none()


def _review_history(db: Session, *, report_id: uuid.UUID) -> list[ReviewEvent]:
    return list(
        db.execute(
            select(ReviewEvent)
            .where(
                ReviewEvent.report_id == report_id,
                ReviewEvent.stage == REVIEW_STAGE_PRE_TRANSLATION,
            )
            .order_by(ReviewEvent.created_at.asc())
        ).scalars().all()
    )


def _build_review_context(
    db: Session, *, user_id: uuid.UUID, report_id: uuid.UUID
) -> dict[str, Any]:
    report = get_report(db, user_id=user_id, report_id=report_id)
    version = _resolve_latest_review_version(db, report_id=report_id)
    if version is None:
        raise ReviewNotFoundError(
            "no humanized or human-review-edited version found for this report"
        )
    events = _review_history(db, report_id=report_id)
    return {
        "report_id": report.id,
        "status": report.status,
        "version_id": version.id,
        "version_number": version.version_number,
        "language": version.language,
        "content": version.content,
        "change_type": version.change_type,
        "source_version_id": version.source_version_id,
        "review_stage": REVIEW_STAGE_PRE_TRANSLATION,
        "review_events": events,
    }


def get_pre_translation_review(
    db: Session, *, user_id: uuid.UUID, report_id: uuid.UUID
) -> dict[str, Any]:
    """Strict GET — requires the report to be in ``pre_translation_review``."""
    report = get_report(db, user_id=user_id, report_id=report_id)
    if report.status != "pre_translation_review":
        raise InvalidReviewStateError(
            f"report status is {report.status!r}, expected 'pre_translation_review'"
        )
    return _build_review_context(db, user_id=user_id, report_id=report_id)


def get_review_context(
    db: Session, *, user_id: uuid.UUID, report_id: uuid.UUID
) -> dict[str, Any]:
    """Non-strict context — used after actions that change status."""
    return _build_review_context(db, user_id=user_id, report_id=report_id)


def get_current_pre_translation_review_version(
    db: Session, *, user_id: uuid.UUID, report_id: uuid.UUID
) -> ReportVersion:
    report = get_report(db, user_id=user_id, report_id=report_id)
    if report.status != "pre_translation_review":
        raise InvalidReviewStateError(
            f"report status is {report.status!r}, expected 'pre_translation_review'"
        )
    latest = _resolve_latest_review_version(db, report_id=report_id)
    if latest is None:
        raise ReviewNotFoundError(
            "no humanized or human-review-edited version found for this report"
        )
    return latest


def _lock_and_load_report(db: Session, report_id: uuid.UUID) -> Report:
    """Acquire a row lock on the report and return a fresh snapshot.

    Uses ``populate_existing=True`` so that any previously cached
    ``Report`` instance in the session is refreshed from the DB — this is
    critical because ``with_for_update()`` alone returns the stale
    session-cached instance without re-reading the row.
    """
    return db.execute(
        select(Report)
        .where(Report.id == report_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).scalar_one()


def edit_pre_translation_review(
    db: Session,
    *,
    user_id: uuid.UUID,
    report_id: uuid.UUID,
    version_id: uuid.UUID,
    content: str,
    notes: str | None = None,
) -> ReportVersion:
    get_report(db, user_id=user_id, report_id=report_id)

    if not isinstance(content, str) or not content.strip():
        raise ReviewValidationError("content must be a non-empty string")
    if len(content) > MAX_CONTENT_LENGTH:
        raise ReviewValidationError(
            f"content exceeds maximum length {MAX_CONTENT_LENGTH}"
        )
    if notes is not None and len(notes) > MAX_NOTES_LENGTH:
        raise ReviewValidationError(
            f"notes exceed maximum length {MAX_NOTES_LENGTH}"
        )

    locked = _lock_and_load_report(db, report_id)

    if locked.status != "pre_translation_review":
        db.rollback()
        raise InvalidReviewStateError(f"report status is {locked.status!r}")

    current = _resolve_latest_review_version(db, report_id=report_id)
    if current is None or current.id != version_id:
        db.rollback()
        raise StaleReviewVersionError(
            "version_id is no longer the active review version"
        )

    diff = {
        "type": "human_review_edit",
        "stage": REVIEW_STAGE_PRE_TRANSLATION,
        "changed": content != current.content,
        "editor_user_id": str(user_id),
        "edited_at": datetime.now(UTC).isoformat(),
    }

    new_version = create_report_version(
        db,
        user_id=user_id,
        report_id=report_id,
        language=current.language,
        content=content,
        created_by_user=True,
        change_type="human_review_edit",
        source_version_id=current.id,
        diff_from_previous=diff,
        commit=False,
    )

    db.add(
        ReviewEvent(
            report_id=report_id,
            stage=REVIEW_STAGE_PRE_TRANSLATION,
            user_id=user_id,
            action=REVIEW_ACTION_EDITED,
            version_id=new_version.id,
            notes=notes,
        )
    )
    db.commit()
    db.refresh(new_version)
    return new_version


def approve_pre_translation_review(
    db: Session,
    *,
    user_id: uuid.UUID,
    report_id: uuid.UUID,
    version_id: uuid.UUID,
) -> Report:
    get_report(db, user_id=user_id, report_id=report_id)

    locked = _lock_and_load_report(db, report_id)

    if locked.status == "translating":
        db.commit()
        return locked

    if locked.status != "pre_translation_review":
        db.rollback()
        raise InvalidReviewStateError(f"report status is {locked.status!r}")

    current = _resolve_latest_review_version(db, report_id=report_id)
    if current is None or current.id != version_id:
        db.rollback()
        raise StaleReviewVersionError(
            "version_id is no longer the active review version"
        )

    db.add(
        ReviewEvent(
            report_id=report_id,
            stage=REVIEW_STAGE_PRE_TRANSLATION,
            user_id=user_id,
            action=REVIEW_ACTION_APPROVED,
            version_id=current.id,
            notes=None,
        )
    )

    update_report_status(
        db,
        user_id=user_id,
        report_id=report_id,
        new_status="translating",
        reason="pre_translation_review_approved",
        commit=False,
    )
    db.commit()  # approval durable BEFORE enqueue
    db.refresh(locked)

    # ---- M16 handoff: enqueue ALWAYS in a separate transaction ----
    try:
        from app.services.translation_jobs import (
            TranslationEnqueueError,
            TranslationEnqueueStateError,
            enqueue_translation_job,
        )
        from app.services.translation_profile import (
            get_current_translation_profile_id,
        )

        target_language = current.language
        report_row = db.get(Report, report_id)
        if report_row is not None and getattr(
            report_row, "output_language", None
        ):
            target_language = report_row.output_language

        enqueue_translation_job(
            db=db,
            user_id=user_id,
            report_id=report_id,
            source_version_id=current.id,
            target_language=target_language,
            profile_id=get_current_translation_profile_id(),
        )
        db.commit()
    except TranslationEnqueueStateError:
        db.rollback()
    except TranslationEnqueueError:
        db.rollback()
        logger.warning(
            "m16_enqueue_after_approval_failed",
            extra={"report_id": str(report_id)},
        )
    except Exception:
        db.rollback()
        logger.exception(
            "m16_enqueue_unexpected_failure",
            extra={"report_id": str(report_id)},
        )

    return locked

def request_changes_pre_translation_review(
    db: Session,
    *,
    user_id: uuid.UUID,
    report_id: uuid.UUID,
    version_id: uuid.UUID,
    notes: str,
) -> Report:
    get_report(db, user_id=user_id, report_id=report_id)

    if not notes or not notes.strip():
        raise ReviewValidationError("notes must be non-empty")
    if len(notes) > MAX_NOTES_LENGTH:
        raise ReviewValidationError(
            f"notes exceed maximum length {MAX_NOTES_LENGTH}"
        )

    locked = _lock_and_load_report(db, report_id)
    if locked.status != "pre_translation_review":
        db.rollback()
        raise InvalidReviewStateError(f"report status is {locked.status!r}")

    current = _resolve_latest_review_version(db, report_id=report_id)
    if current is None or current.id != version_id:
        db.rollback()
        raise StaleReviewVersionError("stale version")

    db.add(
        ReviewEvent(
            report_id=report_id,
            stage=REVIEW_STAGE_PRE_TRANSLATION,
            user_id=user_id,
            action=REVIEW_ACTION_REQUESTED_CHANGES,
            version_id=current.id,
            notes=notes,
        )
    )
    db.commit()
    db.refresh(locked)
    return locked


def reject_pre_translation_review(
    db: Session,
    *,
    user_id: uuid.UUID,
    report_id: uuid.UUID,
    version_id: uuid.UUID,
    notes: str,
) -> Report:
    get_report(db, user_id=user_id, report_id=report_id)

    if not notes or not notes.strip():
        raise ReviewValidationError("notes must be non-empty")
    if len(notes) > MAX_NOTES_LENGTH:
        raise ReviewValidationError(
            f"notes exceed maximum length {MAX_NOTES_LENGTH}"
        )

    locked = _lock_and_load_report(db, report_id)
    if locked.status != "pre_translation_review":
        db.rollback()
        raise InvalidReviewStateError(f"report status is {locked.status!r}")

    current = _resolve_latest_review_version(db, report_id=report_id)
    if current is None or current.id != version_id:
        db.rollback()
        raise StaleReviewVersionError("stale version")

    db.add(
        ReviewEvent(
            report_id=report_id,
            stage=REVIEW_STAGE_PRE_TRANSLATION,
            user_id=user_id,
            action=REVIEW_ACTION_REJECTED,
            version_id=current.id,
            notes=notes,
        )
    )
    db.commit()
    db.refresh(locked)
    return locked
