"""M30 — Worker handler for citation_generate jobs (stale-safe)."""
from __future__ import annotations

import logging
import uuid

from app.db.session import SessionLocal
from app.domain.citation import M30_VERSION
from app.services.citation import context as ctx_svc
from app.services.citation import persistence as persist_svc

logger = logging.getLogger(__name__)


def _uuid(v):
    if v is None:
        return None
    try:
        return uuid.UUID(str(v))
    except (TypeError, ValueError, AttributeError):
        return None


def handle_citation_generate(ctx) -> dict:
    payload = ctx.payload or {}
    report_id = _uuid(payload.get("report_id"))
    version_id = _uuid(payload.get("manuscript_version_id"))
    user_id = _uuid(payload.get("user_id"))
    citation_style = payload.get("citation_style", "author_year")
    payload_context_hash = payload.get("context_hash")
    payload_m30_version = payload.get("m30_version")
    force = bool(payload.get("force", False))

    if report_id is None or version_id is None:
        raise ValueError(
            "citation payload missing report_id/manuscript_version_id"
        )

    with SessionLocal() as db:
        current_context_hash = ctx_svc.compute_m30_context_hash(
            db,
            manuscript_version_id=version_id,
            citation_style=citation_style,
        )
        stale_reason: str | None = None
        if (
            payload_context_hash
            and payload_context_hash != current_context_hash
        ):
            stale_reason = "stale_context"
        elif (
            payload_m30_version
            and payload_m30_version != M30_VERSION
        ):
            stale_reason = "stale_version"

        if stale_reason is not None:
            logger.info(
                "citation_stale report_id=%s version_id=%s reason=%s",
                report_id, version_id, stale_reason,
            )
            return {
                "status": "skipped",
                "skipped": True,
                "reason": stale_reason,
            }

        effective_user = user_id or uuid.UUID(int=0)
        persisted = persist_svc.run_citation_persisted(
            db,
            user_id=effective_user,
            report_id=report_id,
            manuscript_version_id=version_id,
            citation_style=citation_style,
            force=force,
            commit=True,
        )
        return {
            "status": persisted.run.status,
            "skipped": persisted.skipped,
            "run_id": str(persisted.run.id),
            "context_hash": persisted.run.context_hash,
        }


__all__ = ["handle_citation_generate"]
