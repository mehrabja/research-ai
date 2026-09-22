"""M24 — Enqueue helper for research plan generation."""
from __future__ import annotations

import contextlib
import logging
import uuid

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.domain.research_plan import RESEARCH_PLAN_VERSION
from app.services import jobs as jobs_service
from app.services.research_planning import context as context_svc

logger = logging.getLogger(__name__)


def enqueue_research_plan(
    db: Session,
    *,
    project_id: uuid.UUID,
    user_id: uuid.UUID | None,
    force: bool = False,
) -> uuid.UUID | None:
    """Best-effort enqueue. Returns Job id or None on failure.

    Note: ``jobs_service.enqueue_job`` owns its own transaction
    (it calls ``db.commit()`` internally). We must NOT wrap it in a
    savepoint — doing so makes the savepoint context-manager trip
    over a transaction that enqueue_job already committed.
    """
    try:
        context_hash = context_svc.compute_research_planning_hash(
            db, project_id=project_id
        )
        payload = {
            "project_id": str(project_id),
            "user_id": str(user_id) if user_id else None,
            "context_hash": context_hash,
            "planner_version": RESEARCH_PLAN_VERSION,
            "force": bool(force),
        }
        enqueued = jobs_service.enqueue_job(
            db,
            job_type="research_plan_generate",
            payload=payload,
            idempotency_key=(
                f"research_plan_generate:{project_id}:"
                f"{context_hash}:{RESEARCH_PLAN_VERSION}:"
                f"{int(force)}"
            ),
            user_id=user_id,
            max_attempts=getattr(
                get_settings(),
                "research_plan_job_max_attempts", 3,
            ),
        )
        job = getattr(enqueued, "job", enqueued)
        return getattr(job, "id", None)
    except Exception:  # noqa: BLE001
        logger.exception(
            "research_plan_enqueue_failed project_id=%s", project_id
        )
        # Make sure the caller's session is usable again.
        with contextlib.suppress(Exception):
            db.rollback()
        return None
