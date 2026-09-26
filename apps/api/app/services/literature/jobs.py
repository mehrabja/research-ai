"""M23 — Enqueue helper for literature analysis.

Caller owns the transaction. This helper NEVER commits.
On failure it uses a SAVEPOINT so the caller's outer transaction
stays usable; the exception is logged and None is returned.
"""
from __future__ import annotations

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models.literature import LiteratureIntelligenceRun
from app.domain.literature import LITERATURE_INTELLIGENCE_VERSION
from app.services import jobs as jobs_service
from app.services.literature import context

logger = logging.getLogger(__name__)


def enqueue_literature_analysis(
    db: Session,
    *,
    project_id: uuid.UUID,
    user_id: uuid.UUID | None,
    force: bool = False,
) -> uuid.UUID | None:
    """Best-effort enqueue. Returns Job id, or None on failure.

    * Does NOT commit — caller is responsible.
    * Uses a savepoint so a failure here does not poison the
      caller's transaction.
    """
    try:
        context_hash = context.build_literature_context_hash(
            db, project_id=project_id
        )
        payload = {
            "project_id": str(project_id),
            "context_hash": context_hash,
            "analysis_version": LITERATURE_INTELLIGENCE_VERSION,
            "force": bool(force),
            "user_id": str(user_id) if user_id else None,
        }
        with db.begin_nested():
            enqueued = jobs_service.enqueue_job(
                db,
                job_type="literature_analyze",
                payload=payload,
                idempotency_key=(
                    f"literature_analyze:{project_id}:{context_hash}:"
                    f"{LITERATURE_INTELLIGENCE_VERSION}:{int(force)}"
                ),
                user_id=user_id,
                max_attempts=getattr(
                    get_settings(),
                    "literature_job_max_attempts",
                    3,
                ),
            )
            db.flush()
        job = getattr(enqueued, "job", enqueued)
        return getattr(job, "id", None)
    except Exception:  # noqa: BLE001
        logger.exception(
            "literature_enqueue_failed project_id=%s", project_id
        )
        return None


def literature_run_completed(
    db: Session,
    *,
    project_id: uuid.UUID,
    context_hash: str,
    analysis_version: str,
) -> bool:
    row = db.execute(
        select(LiteratureIntelligenceRun.id)
        .where(
            LiteratureIntelligenceRun.project_id == project_id,
            LiteratureIntelligenceRun.context_hash == context_hash,
            LiteratureIntelligenceRun.analysis_version
            == analysis_version,
            LiteratureIntelligenceRun.status == "completed",
        )
        .limit(1)
    ).scalar_one_or_none()
    return row is not None


__all__ = [
    "enqueue_literature_analysis",
    "literature_run_completed",
]
