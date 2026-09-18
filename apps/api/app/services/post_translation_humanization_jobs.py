"""M17 — Post-translation humanization enqueue helpers."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from enum import StrEnum

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.pipeline import TranslationRun, TranslationVersion
from app.db.models.report import Report
from app.domain.humanization import (
    build_post_translation_humanization_job_idempotency_key,
)
from app.domain.jobs import JobTypes
from app.services import jobs as jobs_service

logger = logging.getLogger(__name__)


class PostTranslationHumanizationEnqueueError(Exception): ...
class PostTranslationHumanizationEnqueueOwnershipError(
    PostTranslationHumanizationEnqueueError
): ...
class PostTranslationHumanizationEnqueueStateError(
    PostTranslationHumanizationEnqueueError
): ...


class EnqueueOutcome(StrEnum):
    ENQUEUED = "enqueued"
    ALREADY_EXISTS = "already_exists"
    NOT_ELIGIBLE = "not_eligible"


@dataclass(frozen=True)
class EnqueueResult:
    outcome: EnqueueOutcome
    job_id: uuid.UUID | None


def enqueue_post_translation_humanization_job(
    *,
    db: Session,
    user_id: uuid.UUID,
    report_id: uuid.UUID,
    translation_run_id: uuid.UUID,
    translation_version_id: uuid.UUID,
    policy_version: str,
) -> EnqueueResult:
    report = db.execute(
        select(Report).where(Report.id == report_id)
    ).scalar_one_or_none()
    if report is None or getattr(report, "deleted_at", None) is not None:
        raise PostTranslationHumanizationEnqueueOwnershipError("report not found")
    if getattr(report, "user_id", None) != user_id:
        raise PostTranslationHumanizationEnqueueOwnershipError(
            "report ownership mismatch"
        )

    trun = db.execute(
        select(TranslationRun).where(
            TranslationRun.id == translation_run_id,
            TranslationRun.report_id == report_id,
        )
    ).scalar_one_or_none()
    if trun is None:
        raise PostTranslationHumanizationEnqueueOwnershipError(
            "translation run not found for report"
        )
    if trun.status != "success":
        return EnqueueResult(outcome=EnqueueOutcome.NOT_ELIGIBLE, job_id=None)

    tver = db.execute(
        select(TranslationVersion).where(
            TranslationVersion.id == translation_version_id,
            TranslationVersion.translation_run_id == translation_run_id,
        )
    ).scalar_one_or_none()
    if tver is None:
        raise PostTranslationHumanizationEnqueueOwnershipError(
            "translation version not found for translation run"
        )

    if report.status != "post_translation_review":
        return EnqueueResult(outcome=EnqueueOutcome.NOT_ELIGIBLE, job_id=None)

    idem = build_post_translation_humanization_job_idempotency_key(
        report_id=str(report_id),
        translation_run_id=str(translation_run_id),
        translation_version_id=str(translation_version_id),
        policy_version=policy_version,
    )

    payload = {
        "report_id": str(report_id),
        "translation_run_id": str(translation_run_id),
        "translation_version_id": str(translation_version_id),
        "policy_version": policy_version,
    }

    result = jobs_service.enqueue_job(
        db,
        job_type=JobTypes.HUMANIZE_POST_TRANSLATION.value,
        payload=payload,
        idempotency_key=idem,
        report_id=report_id,
        user_id=user_id,
    )

    job = getattr(result, "job", None)
    if job is None:
        return EnqueueResult(outcome=EnqueueOutcome.ALREADY_EXISTS, job_id=None)

    created = getattr(result, "created", None)
    if created is None:
        created = getattr(result, "was_created", None)

    if created is False:
        return EnqueueResult(outcome=EnqueueOutcome.ALREADY_EXISTS, job_id=job.id)
    return EnqueueResult(outcome=EnqueueOutcome.ENQUEUED, job_id=job.id)
