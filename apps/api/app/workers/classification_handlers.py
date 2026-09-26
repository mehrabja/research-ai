"""M21/M22 — Classification worker handler."""
from __future__ import annotations

import logging
import uuid

from app.db.session import SessionLocal
from app.services import jobs as jobs_service
from app.services.classification.orchestrator import classify_project

logger = logging.getLogger(__name__)


def _parse_uuid(value) -> uuid.UUID | None:
    if value is None:
        return None
    return uuid.UUID(str(value))


def handle_research_classification(ctx) -> dict:
    """Idempotent classification job.

    No-ops on:
      * payload missing ``project_id`` (raises, since that's a bug);
      * project not existing (was likely deleted);
      * archived project.

    Skips the expensive context build if the payload's
    ``context_hash`` already has a completed-like run.
    """
    from app.db.models.project import Project

    payload = ctx.payload or {}
    project_id_raw = payload.get("project_id")
    if not project_id_raw:
        raise ValueError("classification payload missing project_id")

    project_id: uuid.UUID = uuid.UUID(str(project_id_raw))
    context_hash = payload.get("context_hash")
    user_id = _parse_uuid(payload.get("user_id"))

    with SessionLocal() as db:
        project = db.get(Project, project_id)
        if project is None:
            logger.warning(
                "classification_project_missing project_id=%s",
                project_id,
            )
            return {"status": "project_not_found"}

        if getattr(project, "status", None) == "archived":
            logger.info(
                "classification_project_archived project_id=%s",
                project_id,
            )
            return {"status": "project_archived"}

        if context_hash and jobs_service.classification_already_completed(
            db, project_id=project_id, context_hash=context_hash
        ):
            logger.info(
                "classification_already_completed project_id=%s",
                project_id,
            )
            return {"status": "already_completed"}

        row = classify_project(
            db, project_id=project_id, user_id=user_id
        )
        return {
            "status": row.status,
            "classification_id": str(row.id),
        }
