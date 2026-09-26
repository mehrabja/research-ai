"""M30 — Enqueue helper for citation jobs."""
from __future__ import annotations

import logging
import uuid

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models.manuscript import Manuscript, ManuscriptVersion
from app.db.models.report import Report
from app.domain.citation import M30_VERSION, CitationStyle
from app.services import jobs as jobs_service
from app.services.citation import context as ctx_svc
from app.services.reports import get_report

logger = logging.getLogger(__name__)


def enqueue_citation_run(
    db: Session,
    *,
    report_id: uuid.UUID,
    manuscript_version_id: uuid.UUID,
    user_id: uuid.UUID,
    citation_style: str = CitationStyle.AUTHOR_YEAR.value,
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

    context_hash = ctx_svc.compute_m30_context_hash(
        db,
        manuscript_version_id=manuscript_version_id,
        citation_style=citation_style,
    )
    payload = {
        "report_id": str(report_id),
        "manuscript_version_id": str(manuscript_version_id),
        "user_id": str(user_id),
        "context_hash": context_hash,
        "m30_version": M30_VERSION,
        "citation_style": citation_style,
        "force": bool(force),
    }
    settings = get_settings()
    enqueued = jobs_service.enqueue_job(
        db,
        job_type="citation_generate",
        payload=payload,
        idempotency_key=(
            f"citation:{report_id}:{manuscript_version_id}:"
            f"{context_hash}:{M30_VERSION}:{citation_style}"
        ),
        report_id=report_id,
        user_id=user_id,
        max_attempts=int(settings.citation_job_max_attempts),
    )
    return enqueued.job.id


__all__ = ["enqueue_citation_run"]
