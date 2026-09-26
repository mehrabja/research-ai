"""M28.5 — Worker handler for manuscript_prose_generate jobs."""
from __future__ import annotations

import logging
import uuid

from app.db.session import SessionLocal
from app.domain.manuscript_prose import M28_5_VERSION
from app.services.manuscript_prose import context as ctx_svc
from app.services.manuscript_prose import persistence as persist_svc

logger = logging.getLogger(__name__)


def _uuid(v):
    if v is None:
        return None
    try:
        return uuid.UUID(str(v))
    except (TypeError, ValueError, AttributeError):
        return None


def handle_manuscript_prose_generate(ctx) -> dict:
    payload = ctx.payload or {}
    report_id = _uuid(payload.get("report_id"))
    base_version_id = _uuid(payload.get("base_manuscript_version_id"))
    if report_id is None or base_version_id is None:
        raise ValueError(
            "manuscript_prose payload missing ids"
        )

    mode = payload.get("mode")
    payload_context_hash = payload.get("context_hash")
    payload_version = payload.get("m28_5_version")
    force = bool(payload.get("force", False))

    with SessionLocal() as db:
        from app.core.config import get_settings
        s = get_settings()
        current_context_hash = ctx_svc.compute_m28_5_context_hash(
            db,
            manuscript_version_id=base_version_id,
            mode=mode or s.manuscript_prose_default_mode,
            provider=s.manuscript_prose_provider or None,
            model=s.manuscript_prose_model or None,
        )

        stale_reason: str | None = None
        if (
            payload_context_hash
            and payload_context_hash != current_context_hash
        ):
            stale_reason = "stale_context"
        elif (
            payload_version
            and payload_version != M28_5_VERSION
        ):
            stale_reason = "stale_version"

        if stale_reason is not None:
            logger.info(
                "manuscript_prose_stale report_id=%s base_version=%s "
                "reason=%s",
                report_id, base_version_id, stale_reason,
            )
            return {
                "status": "skipped",
                "skipped": True,
                "reason": stale_reason,
            }

        persisted = persist_svc.run_m28_5_persisted(
            db,
            report_id=report_id,
            base_manuscript_version_id=base_version_id,
            mode=mode,
            force=force,
            commit=True,
        )
        return {
            "status": persisted.run.status,
            "skipped": persisted.skipped,
            "run_id": str(persisted.run.id),
            "context_hash": persisted.run.context_hash,
            "section_count": int(persisted.run.section_count or 0),
            "word_count": int(persisted.run.word_count or 0),
        }


__all__ = ["handle_manuscript_prose_generate"]
