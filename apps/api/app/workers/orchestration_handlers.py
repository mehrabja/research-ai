"""M35 — Worker handler for orchestration_run jobs (stale-safe)."""
from __future__ import annotations

import logging
import uuid

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.domain.orchestration import M35_VERSION
from app.services.orchestration import budgets as budget_svc
from app.services.orchestration import context as ctx_svc
from app.services.orchestration import persistence as persist_svc

logger = logging.getLogger(__name__)


def _uuid(v):
    if v is None:
        return None
    try:
        return uuid.UUID(str(v))
    except (TypeError, ValueError, AttributeError):
        return None


def handle_orchestration_run(ctx) -> dict:
    payload = ctx.payload or {}
    project_id = _uuid(payload.get("project_id"))
    report_id = _uuid(payload.get("report_id"))
    user_id = _uuid(payload.get("user_id"))
    if project_id is None or report_id is None:
        raise ValueError(
            "orchestration payload missing project_id/report_id"
        )

    goal = str(payload.get("goal") or "")
    strategy = str(payload.get("strategy") or "")
    inner_payload = payload.get("payload") or {}
    if not isinstance(inner_payload, dict):
        inner_payload = {}
    payload_context_hash = payload.get("context_hash")
    payload_m35_version = payload.get("m35_version")
    force = bool(payload.get("force", False))

    with SessionLocal() as db:
        current_context_hash = ctx_svc.compute_m35_context_hash(
            db,
            project_id=project_id,
            report_id=report_id,
            goal=goal,
            strategy=strategy,
            budget=budget_svc.effective_budget(get_settings()),
        )

        stale_reason: str | None = None
        if (
            payload_context_hash
            and payload_context_hash != current_context_hash
        ):
            stale_reason = "stale_context"
        elif (
            payload_m35_version
            and payload_m35_version != M35_VERSION
        ):
            stale_reason = "stale_version"

        if stale_reason is not None:
            logger.info(
                "orchestration_stale project_id=%s report_id=%s "
                "reason=%s",
                project_id, report_id, stale_reason,
            )
            return {
                "status": "skipped",
                "skipped": True,
                "reason": stale_reason,
            }

        persisted = persist_svc.run_m35_persisted(
            db,
            project_id=project_id,
            report_id=report_id,
            user_id=user_id,
            goal=goal,
            strategy=strategy,
            payload=inner_payload,
            force=force,
            commit=True,
        )
        return {
            "status": persisted.run.status,
            "skipped": persisted.skipped,
            "run_id": str(persisted.run.id),
            "context_hash": persisted.run.context_hash,
            "node_count": int(persisted.run.node_count or 0),
            "completed_node_count": int(
                persisted.run.completed_node_count or 0
            ),
        }


__all__ = ["handle_orchestration_run"]
