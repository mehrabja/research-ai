"""M29 — Worker handler for technical_intelligence jobs (stale-safe)."""
from __future__ import annotations

import logging
import uuid

from app.db.session import SessionLocal
from app.domain.technical_intelligence import M29_VERSION
from app.services.technical_intelligence import context as ctx_svc
from app.services.technical_intelligence import persistence as persist_svc

logger = logging.getLogger(__name__)


def _parse_uuid(v):
    if v is None:
        return None
    try:
        return uuid.UUID(str(v))
    except (ValueError, TypeError, AttributeError):
        return None


def handle_technical_intelligence(ctx) -> dict:
    payload = ctx.payload or {}
    project_id = _parse_uuid(payload.get("project_id"))
    if project_id is None:
        raise ValueError(
            "technical_intelligence payload missing project_id"
        )

    payload_context_hash = payload.get("context_hash")
    payload_m29_version = payload.get("m29_version")
    force = bool(payload.get("force", False))

    with SessionLocal() as db:
        current_context_hash = ctx_svc.compute_m29_context_hash(
            db, project_id=project_id,
        )

        stale_reason: str | None = None
        if (
            payload_context_hash
            and payload_context_hash != current_context_hash
        ):
            stale_reason = "stale_context"
        elif (
            payload_m29_version
            and payload_m29_version != M29_VERSION
        ):
            stale_reason = "stale_version"

        if stale_reason is not None:
            logger.info(
                "technical_intelligence_stale project_id=%s reason=%s",
                project_id, stale_reason,
            )
            return {
                "status": "skipped",
                "skipped": True,
                "reason": stale_reason,
            }

        persisted = persist_svc.run_m29_persisted(
            db,
            project_id=project_id,
            force=force,
            commit=True,
        )
        return {
            "status": persisted.run.status,
            "skipped": persisted.skipped,
            "run_id": str(persisted.run.id),
            "context_hash": persisted.run.context_hash,
        }


__all__ = ["handle_technical_intelligence"]
