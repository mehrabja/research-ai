"""M23 — Literature analysis worker handler."""
from __future__ import annotations

import logging
import uuid

from app.db.session import SessionLocal
from app.services.literature import pipeline
from app.services.literature.jobs import literature_run_completed

logger = logging.getLogger(__name__)


def _parse_uuid(value) -> uuid.UUID | None:
    if value is None:
        return None
    return uuid.UUID(str(value))


def handle_literature_analyze(ctx) -> dict:
    payload = ctx.payload or {}
    project_id_raw = payload.get("project_id")
    if not project_id_raw:
        raise ValueError("literature payload missing project_id")

    project_id = _parse_uuid(project_id_raw)
    if project_id is None:
        raise ValueError("literature payload project_id invalid")
    context_hash = payload.get("context_hash")
    analysis_version = payload.get("analysis_version")
    force = bool(payload.get("force", False))
    user_id = _parse_uuid(payload.get("user_id"))

    with SessionLocal() as db:
        if (
            not force
            and context_hash
            and analysis_version
            and literature_run_completed(
                db,
                project_id=project_id,
                context_hash=context_hash,
                analysis_version=analysis_version,
            )
        ):
            logger.info(
                "literature_already_completed project_id=%s",
                project_id,
            )
            return {"status": "already_completed"}

        result = pipeline.run_literature_analysis(
            db,
            user_id=user_id,
            project_id=project_id,
            force=force,
            commit=True,
        )
        return {
            "status": result.run.status,
            "run_id": str(result.run.id),
            "skipped": result.skipped,
        }


__all__ = ["handle_literature_analyze"]
