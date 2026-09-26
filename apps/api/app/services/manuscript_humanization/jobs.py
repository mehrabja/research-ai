"""M32 — Enqueue helper for manuscript humanization jobs."""
from __future__ import annotations

import logging
import uuid

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models.manuscript import Manuscript, ManuscriptVersion
from app.db.models.report import Report
from app.domain.humanization_m32 import M32_VERSION
from app.services import jobs as jobs_service
from app.services.manuscript_humanization import context as ctx_svc
from app.services.reports import get_report

logger = logging.getLogger(__name__)


def enqueue_manuscript_humanization(
    db: Session,
    *,
    report_id: uuid.UUID,
    manuscript_version_id: uuid.UUID,
    user_id: uuid.UUID,
    mode: str,
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

    context_hash = ctx_svc.compute_m32_context_hash(
        db,
        manuscript_version_id=manuscript_version_id,
        mode=mode,
    )
    payload = {
        "report_id": str(report_id),
        "manuscript_version_id": str(manuscript_version_id),
        "user_id": str(user_id),
        "mode": mode,
        "context_hash": context_hash,
        "m32_version": M32_VERSION,
        "force": bool(force),
    }
    settings = get_settings()
    enqueued = jobs_service.enqueue_job(
        db,
        job_type="manuscript_humanization",
        payload=payload,
        idempotency_key=(
            f"manuscript_humanization:{report_id}:"
            f"{manuscript_version_id}:{context_hash}:"
            f"{M32_VERSION}:{mode}"
        ),
        report_id=report_id,
        user_id=user_id,
        max_attempts=int(
            settings.manuscript_humanization_job_max_attempts
        ),
    )
    return enqueued.job.id


__all__ = ["enqueue_manuscript_humanization"]
