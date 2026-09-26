"""M31 — Worker handler for academic_qa_generate jobs (stale-safe)."""
from __future__ import annotations

import logging
import uuid

from app.db.session import SessionLocal
from app.domain.academic_qa import M31_VERSION, QA_RULES_VERSION
from app.services.academic_qa import context as ctx_svc
from app.services.academic_qa import persistence as persist_svc

logger = logging.getLogger(__name__)


def _uuid(v):
    if v is None:
        return None
    try:
        return uuid.UUID(str(v))
    except (TypeError, ValueError, AttributeError):
        return None


def handle_academic_qa_generate(ctx) -> dict:
    payload = ctx.payload or {}
    report_id = _uuid(payload.get("report_id"))
    version_id = _uuid(payload.get("manuscript_version_id"))
    if report_id is None or version_id is None:
        raise ValueError(
            "academic_qa payload missing report_id/manuscript_version_id"
        )

    payload_context_hash = payload.get("context_hash")
    payload_m31_version = payload.get("m31_version")
    payload_rules_version = payload.get("rules_version")
    force = bool(payload.get("force", False))

    with SessionLocal() as db:
        current_context_hash = ctx_svc.compute_m31_context_hash(
            db, manuscript_version_id=version_id,
        )

        stale_reason: str | None = None
        if (
            payload_context_hash
            and payload_context_hash != current_context_hash
        ):
            stale_reason = "stale_context"
        elif (
            payload_m31_version
            and payload_m31_version != M31_VERSION
        ):
            stale_reason = "stale_version"
        elif (
            payload_rules_version
            and payload_rules_version != QA_RULES_VERSION
        ):
            stale_reason = "stale_rules"

        if stale_reason is not None:
            logger.info(
                "academic_qa_stale report_id=%s version_id=%s reason=%s",
                report_id, version_id, stale_reason,
            )
            return {
                "status": "skipped",
                "skipped": True,
                "reason": stale_reason,
            }

        persisted = persist_svc.run_m31_persisted(
            db,
            report_id=report_id,
            manuscript_version_id=version_id,
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


__all__ = ["handle_academic_qa_generate"]
