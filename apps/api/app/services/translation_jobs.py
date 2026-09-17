"""M16 — Translation job enqueue helper."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.report import Report, ReportVersion, ReviewEvent
from app.domain.jobs import JobTypes
from app.services import jobs as jobs_service


class TranslationEnqueueError(Exception): ...
class TranslationEnqueueOwnershipError(TranslationEnqueueError): ...
class TranslationEnqueueStateError(TranslationEnqueueError): ...


def build_translation_job_idempotency_key(
    *,
    report_id: uuid.UUID | str,
    source_version_id: uuid.UUID | str,
    target_language: str,
    profile_id: str,
) -> str:
    return (
        f"translate_report:{report_id}:{source_version_id}:"
        f"{target_language}:{profile_id}"
    )


def _resolve_m15_approved_version_id(
    db: Session, *, report_id: uuid.UUID
) -> uuid.UUID | None:
    event = db.execute(
        select(ReviewEvent)
        .where(
            ReviewEvent.report_id == report_id,
            ReviewEvent.stage == "pre_translation",
            ReviewEvent.action == "approved",
        )
        .order_by(ReviewEvent.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    return event.version_id if event is not None else None


def enqueue_translation_job(
    *,
    db: Session,
    user_id: uuid.UUID,
    report_id: uuid.UUID,
    source_version_id: uuid.UUID,
    target_language: str,
    profile_id: str,
) -> uuid.UUID:
    report = db.execute(
        select(Report).where(Report.id == report_id)
    ).scalar_one_or_none()
    if report is None or getattr(report, "deleted_at", None) is not None:
        raise TranslationEnqueueOwnershipError("report not found")
    if getattr(report, "user_id", None) != user_id:
        raise TranslationEnqueueOwnershipError("report ownership mismatch")

    version = db.execute(
        select(ReportVersion).where(
            ReportVersion.id == source_version_id,
            ReportVersion.report_id == report_id,
        )
    ).scalar_one_or_none()
    if version is None:
        raise TranslationEnqueueOwnershipError(
            "source version not found for report"
        )

    approved_version_id = _resolve_m15_approved_version_id(
        db, report_id=report_id
    )
    if approved_version_id is None or approved_version_id != source_version_id:
        raise TranslationEnqueueStateError(
            "source_version_id is not the M15-approved version"
        )

    # Recovery path: only from `translating` — approval moved us here.
    if report.status != "translating":
        raise TranslationEnqueueStateError(
            f"report status {report.status!r} not eligible for translation enqueue"
        )

    idem = build_translation_job_idempotency_key(
        report_id=report_id,
        source_version_id=source_version_id,
        target_language=target_language,
        profile_id=profile_id,
    )

    payload = {
        "report_id": str(report_id),
        "source_version_id": str(source_version_id),
        "target_language": target_language,
        "profile_id": profile_id,
    }

    result = jobs_service.enqueue_job(
        db,
        job_type=JobTypes.TRANSLATE_REPORT.value,
        payload=payload,
        idempotency_key=idem,
        report_id=report_id,
        user_id=user_id,
    )
    return result.job.id
