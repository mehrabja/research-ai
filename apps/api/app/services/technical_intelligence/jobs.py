"""M29 — Enqueue helper for technical intelligence jobs."""
from __future__ import annotations

import logging
import uuid

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.domain.technical_intelligence import M29_VERSION
from app.services import jobs as jobs_service
from app.services.projects import get_project
from app.services.technical_intelligence import context as ctx_svc

logger = logging.getLogger(__name__)


def enqueue_technical_intelligence(
    db: Session,
    *,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    force: bool = False,
) -> uuid.UUID:
    get_project(db, user_id=user_id, project_id=project_id)

    context_hash = ctx_svc.compute_m29_context_hash(
        db, project_id=project_id
    )
    payload = {
        "project_id": str(project_id),
        "user_id": str(user_id),
        "context_hash": context_hash,
        "m29_version": M29_VERSION,
        "force": bool(force),
    }

    settings = get_settings()
    enqueued = jobs_service.enqueue_job(
        db,
        job_type="technical_intelligence",
        payload=payload,
        idempotency_key=(
            f"technical_intelligence:{project_id}:"
            f"{context_hash}:{M29_VERSION}"
        ),
        user_id=user_id,
        max_attempts=int(
            settings.technical_intelligence_job_max_attempts
        ),
    )
    return enqueued.job.id


__all__ = ["enqueue_technical_intelligence"]
