"""M31 — Enqueue helper for academic QA jobs."""
from __future__ import annotations

import logging
import uuid

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models.manuscript import Manuscript, ManuscriptVersion
from app.db.models.report import Report
from app.domain.academic_qa import M31_VERSION, QA_RULES_VERSION
from app.services import jobs as jobs_service
from app.services.academic_qa import context as ctx_svc
from app.services.reports import get_report

logger = logging.getLogger(__name__)


def enqueue_academic_qa(
    db: Session,
    *,
    report_id: uuid.UUID,
    manuscript_version_id: uuid.UUID,
    user_id: uuid.UUID,
    force: bool = False,
) -> uuid.UUID:
    get_report(db, user_id=user_id, report_id=report_id)
    report = db.get(Report, report_id)
    version = db.get(ManuscriptVersion, manuscript_version_id)
    if report is None or version is None:
        raise ValueError("report or version missing")
    ms = db.get(Manuscript, version.manuscript_id)
    if ms is None or ms.report_id != report_id:
        raise ValueError("manuscript mismatch")

    context_hash = ctx_svc.compute_m31_context_hash(
        db, manuscript_version_id=manuscript_version_id,
    )
    payload = {
        "report_id": str(report_id),
        "manuscript_version_id": str(manuscript_version_id),
        "user_id": str(user_id),
        "context_hash": context_hash,
        "m31_version": M31_VERSION,
        "rules_version": QA_RULES_VERSION,
        "force": bool(force),
    }
    settings = get_settings()
    enqueued = jobs_service.enqueue_job(
        db,
        job_type="academic_qa_generate",
        payload=payload,
        idempotency_key=(
            f"academic_qa:{report_id}:{manuscript_version_id}:"
            f"{context_hash}:{M31_VERSION}:{QA_RULES_VERSION}"
        ),
        report_id=report_id,
        user_id=user_id,
        max_attempts=int(settings.academic_qa_job_max_attempts),
    )
    return enqueued.job.id


__all__ = ["enqueue_academic_qa"]
