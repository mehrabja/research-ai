"""M27 — Manuscript generate worker handler (stale-context safe)."""
from __future__ import annotations

import logging
import uuid

from app.db.models.report import Report
from app.db.session import SessionLocal
from app.services.manuscript import builder as builder_svc
from app.services.manuscript import context as ctx_svc
from app.services.projects import get_project

logger = logging.getLogger(__name__)


def _parse_uuid(value) -> uuid.UUID | None:
    if value is None:
        return None
    try:
        return uuid.UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        return None


def handle_manuscript_generate(ctx) -> dict:
    payload = ctx.payload or {}
    report_id = _parse_uuid(payload.get("report_id"))
    if report_id is None:
        raise ValueError("manuscript payload missing report_id")

    user_id = _parse_uuid(payload.get("user_id"))
    force = bool(payload.get("force", False))
    payload_context_hash = payload.get("context_hash")

    with SessionLocal() as db:
        report = db.get(Report, report_id)
        if report is None:
            raise ValueError("manuscript report not found")

        effective_user_id = user_id or report.user_id
        if user_id is not None and report.user_id != user_id:
            raise ValueError(
                "manuscript payload user does not own report"
            )

        if report.project_id is None:
            return {
                "status": "skipped",
                "skipped": True,
                "reason": "report_has_no_project",
            }

        project = get_project(
            db,
            user_id=effective_user_id,
            project_id=report.project_id,
        )

        plan = ctx_svc.resolve_ready_plan(db, project_id=project.id)
        if plan is None:
            return {
                "status": "skipped",
                "skipped": True,
                "reason": "no_ready_research_plan",
            }

        current_hash = ctx_svc.compute_manuscript_context_hash(
            db, report=report, project=project, plan=plan
        )

        if payload_context_hash and payload_context_hash != current_hash:
            logger.info(
                "manuscript_worker_stale_context report_id=%s "
                "payload=%s current=%s",
                report_id, payload_context_hash, current_hash,
            )
            return {
                "status": "skipped",
                "skipped": True,
                "reason": "stale_context",
                "payload_context_hash": payload_context_hash,
                "current_context_hash": current_hash,
            }

        result = builder_svc.generate_manuscript(
            db,
            user_id=effective_user_id,
            report_id=report_id,
            force=force,
            commit=True,
        )
        return {
            "status": result.run.status,
            "skipped": result.skipped,
            "manuscript_id": (
                str(result.manuscript.id) if result.manuscript else None
            ),
            "version_id": (
                str(result.version.id) if result.version else None
            ),
            "context_hash": result.run.context_hash,
        }


__all__ = ["handle_manuscript_generate"]
