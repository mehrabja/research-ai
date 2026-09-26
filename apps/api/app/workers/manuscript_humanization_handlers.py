"""M32 — Worker handler for manuscript_humanization jobs (stale-safe)."""
from __future__ import annotations

import logging
import uuid

from app.db.session import SessionLocal
from app.domain.humanization_m32 import M32_VERSION
from app.services.manuscript_humanization import context as ctx_svc
from app.services.manuscript_humanization import persistence as persist_svc

logger = logging.getLogger(__name__)


def _uuid(v):
    if v is None:
        return None
    try:
        return uuid.UUID(str(v))
    except (TypeError, ValueError, AttributeError):
        return None


def handle_manuscript_humanization(ctx) -> dict:
    payload = ctx.payload or {}
    report_id = _uuid(payload.get("report_id"))
    version_id = _uuid(payload.get("manuscript_version_id"))
    mode = payload.get("mode", "academic")
    if report_id is None or version_id is None:
        raise ValueError(
            "manuscript_humanization payload missing ids"
        )

    payload_context_hash = payload.get("context_hash")
    payload_m32_version = payload.get("m32_version")
    force = bool(payload.get("force", False))

    with SessionLocal() as db:
        current_context_hash = ctx_svc.compute_m32_context_hash(
            db,
            manuscript_version_id=version_id,
            mode=mode,
        )

        stale_reason: str | None = None
        if (
            payload_context_hash
            and payload_context_hash != current_context_hash
        ):
            stale_reason = "stale_context"
        elif (
            payload_m32_version
            and payload_m32_version != M32_VERSION
        ):
            stale_reason = "stale_version"

        if stale_reason is not None:
            logger.info(
                "manuscript_humanization_stale report_id=%s "
                "version_id=%s reason=%s",
                report_id, version_id, stale_reason,
            )
            return {
                "status": "skipped",
                "skipped": True,
                "reason": stale_reason,
            }

        persisted = persist_svc.run_m32_persisted(
            db,
            report_id=report_id,
            manuscript_version_id=version_id,
            mode=mode,
            force=force,
            commit=True,
        )
        return {
            "status": persisted.run.status,
            "skipped": persisted.skipped,
            "run_id": str(persisted.run.id),
            "context_hash": persisted.run.context_hash,
            "gate": persisted.run.gate,
        }


__all__ = ["handle_manuscript_humanization"]
