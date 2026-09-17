"""M14 — Humanization job enqueue helpers."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.pipeline import DetectionRun
from app.db.models.report import Report, ReportVersion
from app.domain.humanization import (
    DETECTION_STATUS_COMPLETED,
    build_humanization_job_idempotency_key,
)
from app.domain.jobs import JobTypes
from app.domain.report_status import ReportStatus
from app.services.humanization_profile import build_policy_from_settings


class HumanizationEnqueueError(Exception): ...
class HumanizationEnqueueOwnershipError(HumanizationEnqueueError): ...
class HumanizationEnqueueStateError(HumanizationEnqueueError): ...


def build_humanization_job_idempotency_key_for_run(
    *,
    report_id: uuid.UUID | str,
    version_id: uuid.UUID | str,
    detection_run_id: uuid.UUID | str,
    policy_version: str | None = None,
) -> str:
    policy = build_policy_from_settings(version=policy_version)
    return build_humanization_job_idempotency_key(
        report_id=str(report_id),
        version_id=str(version_id),
        detection_run_id=str(detection_run_id),
        policy_version=policy.version,
    )


def enqueue_humanization_job(
    *,
    db: Session,
    user_id: uuid.UUID,
    report_id: uuid.UUID,
    version_id: uuid.UUID,
    detection_run_id: uuid.UUID,
    jobs_service,
    policy_version: str | None = None,
) -> uuid.UUID:
    report = db.execute(select(Report).where(Report.id == report_id)).scalar_one_or_none()
    if report is None or getattr(report, "is_deleted", False):
        raise HumanizationEnqueueOwnershipError("report not found")
    if getattr(report, "user_id", None) != user_id:
        raise HumanizationEnqueueOwnershipError("report ownership mismatch")

    version = db.execute(
        select(ReportVersion).where(
            ReportVersion.id == version_id, ReportVersion.report_id == report_id
        )
    ).scalar_one_or_none()
    if version is None:
        raise HumanizationEnqueueOwnershipError("version not found")

    detection = db.execute(
        select(DetectionRun).where(
            DetectionRun.id == detection_run_id, DetectionRun.report_id == report_id
        )
    ).scalar_one_or_none()
    if detection is None:
        raise HumanizationEnqueueOwnershipError("detection run not found")
    if getattr(detection, "version_id", None) != version_id:
        raise HumanizationEnqueueOwnershipError("detection version mismatch")
    if getattr(detection, "status", None) != DETECTION_STATUS_COMPLETED:
        raise HumanizationEnqueueStateError("detection run not completed")

    if getattr(report, "status", None) != ReportStatus.HUMANIZING.value:
        raise HumanizationEnqueueStateError(
            f"report status {getattr(report, 'status', None)!r} != humanizing"
        )

    policy = build_policy_from_settings(version=policy_version)

    idem = build_humanization_job_idempotency_key(
        report_id=str(report_id),
        version_id=str(version_id),
        detection_run_id=str(detection_run_id),
        policy_version=policy.version,
    )

    payload = {
        "report_id": str(report_id),
        "version_id": str(version_id),
        "detection_run_id": str(detection_run_id),
        "policy_version": policy.version,
    }

    job = jobs_service.enqueue_job(
        db=db,
        user_id=user_id,
        report_id=report_id,
        job_type=JobTypes.HUMANIZE_REPORT.value,
        payload=payload,
        idempotency_key=idem,
    )
    return getattr(job, "id", job)
