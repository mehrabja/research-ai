"""M28.5 — Enqueue helper."""
from __future__ import annotations

import logging
import uuid

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models.manuscript import Manuscript, ManuscriptVersion
from app.db.models.report import Report
from app.domain.manuscript_prose import M28_5_VERSION
from app.services import jobs as jobs_service
from app.services.manuscript_prose import context as ctx_svc
from app.services.reports import get_report

logger = logging.getLogger(__name__)


def enqueue_manuscript_prose(
    db: Session,
    *,
    report_id: uuid.UUID,
    base_manuscript_version_id: uuid.UUID,
    user_id: uuid.UUID,
    mode: str | None = None,
    force: bool = False,
) -> uuid.UUID:
    get_report(db, user_id=user_id, report_id=report_id)
    report = db.get(Report, report_id)
    version = db.get(ManuscriptVersion, base_manuscript_version_id)
    if report is None or version is None:
        raise ValueError("report or version missing")
    ms = db.get(Manuscript, version.manuscript_id)
    if ms is None or ms.report_id != report_id:
        raise ValueError("manuscript mismatch")

    settings = get_settings()
    effective_mode = mode or settings.manuscript_prose_default_mode
    context_hash = ctx_svc.compute_m28_5_context_hash(
        db,
        manuscript_version_id=base_manuscript_version_id,
        mode=effective_mode,
        provider=settings.manuscript_prose_provider or None,
        model=settings.manuscript_prose_model or None,
    )
    payload = {
        "report_id": str(report_id),
        "base_manuscript_version_id": str(base_manuscript_version_id),
        "user_id": str(user_id),
        "mode": effective_mode,
        "context_hash": context_hash,
        "m28_5_version": M28_5_VERSION,
        "force": bool(force),
    }
    enqueued = jobs_service.enqueue_job(
        db,
        job_type="manuscript_prose_generate",
        payload=payload,
        idempotency_key=(
            f"manuscript_prose:{report_id}:"
            f"{base_manuscript_version_id}:{context_hash}:"
            f"{M28_5_VERSION}"
        ),
        report_id=report_id,
        user_id=user_id,
        max_attempts=int(settings.manuscript_prose_job_max_attempts),
    )
    return enqueued.job.id


__all__ = ["enqueue_manuscript_prose"]
