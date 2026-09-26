"""M25 — Enqueue helper for knowledge graph builds."""
from __future__ import annotations

import contextlib
import logging
import uuid

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.domain.knowledge_graph import KNOWLEDGE_GRAPH_VERSION
from app.services import jobs as jobs_service
from app.services.knowledge_graph import context as ctx_svc

logger = logging.getLogger(__name__)


def enqueue_knowledge_graph(
    db: Session,
    *,
    project_id: uuid.UUID,
    user_id: uuid.UUID | None,
    force: bool = False,
) -> uuid.UUID | None:
    """Best-effort enqueue. Returns Job id or None on failure."""
    try:
        context_hash = ctx_svc.compute_graph_context_hash(
            db, project_id=project_id
        )
        payload = {
            "project_id": str(project_id),
            "user_id": str(user_id) if user_id else None,
            "context_hash": context_hash,
            "graph_version": KNOWLEDGE_GRAPH_VERSION,
            "force": bool(force),
        }
        enqueued = jobs_service.enqueue_job(
            db,
            job_type="knowledge_graph_build",
            payload=payload,
            idempotency_key=(
                f"knowledge_graph_build:{project_id}:"
                f"{context_hash}:{KNOWLEDGE_GRAPH_VERSION}:"
                f"{int(force)}"
            ),
            user_id=user_id,
            max_attempts=getattr(
                get_settings(),
                "knowledge_graph_job_max_attempts", 3,
            ),
        )
        job = getattr(enqueued, "job", enqueued)
        return getattr(job, "id", None)
    except Exception:  # noqa: BLE001
        logger.exception(
            "knowledge_graph_enqueue_failed project_id=%s", project_id
        )
        with contextlib.suppress(Exception):
            db.rollback()
        return None
