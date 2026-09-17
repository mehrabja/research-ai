"""Enqueue helpers for detection jobs."""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.detection import hash_detection_input
from app.domain.jobs import JobTypes
from app.services import jobs as jobs_service
from app.services.detection_profile import (
    get_current_detection_profile_id,
)
from app.services.reports import get_report


def build_detection_job_idempotency_key(
    *,
    report_id: uuid.UUID,
    version_id: uuid.UUID,
    profile_id: str,
    input_hash: str,
) -> str:
    return (
        f"detect_report:{report_id}:{version_id}:"
        f"{profile_id}:{input_hash}"
    )


def enqueue_detection_job(
    db: Session,
    *,
    user_id: uuid.UUID,
    report_id: uuid.UUID,
    version_id: uuid.UUID,
    idempotency_key: str | None = None,
    priority: int = 0,
    max_attempts: int | None = None,
) -> jobs_service.EnqueueResult:
    get_report(db, user_id=user_id, report_id=report_id)

    from app.db.models.report import ReportVersion

    version = db.execute(
        select(ReportVersion).where(
            ReportVersion.id == version_id,
            ReportVersion.report_id == report_id,
        )
    ).scalar_one_or_none()
    if version is None:
        from app.core.exceptions import ReportVersionNotFound
        raise ReportVersionNotFound()

    profile_id = get_current_detection_profile_id()
    input_hash = hash_detection_input(version.content or "")

    effective_key = (
        idempotency_key
        or build_detection_job_idempotency_key(
            report_id=report_id,
            version_id=version_id,
            profile_id=profile_id,
            input_hash=input_hash,
        )
    )

    return jobs_service.enqueue_job(
        db,
        job_type=JobTypes.DETECT_REPORT,
        payload={
            "report_id": str(report_id),
            "version_id": str(version_id),
        },
        idempotency_key=effective_key,
        report_id=report_id,
        user_id=user_id,
        priority=priority,
        max_attempts=max_attempts,
    )


__all__ = [
    "build_detection_job_idempotency_key",
    "enqueue_detection_job",
]
