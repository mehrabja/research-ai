"""M35 — Enqueue helper for orchestration jobs."""
from __future__ import annotations

import logging
import uuid

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models.report import Report
from app.domain.orchestration import M35_VERSION
from app.services import jobs as jobs_service
from app.services.orchestration import context as ctx_svc
from app.services.reports import get_report

logger = logging.getLogger(__name__)


def enqueue_orchestration(
    db: Session,
    *,
    project_id: uuid.UUID,
    report_id: uuid.UUID,
    user_id: uuid.UUID,
    goal: str,
    strategy: str,
    payload: dict | None = None,
    force: bool = False,
) -> uuid.UUID:
    get_report(db, user_id=user_id, report_id=report_id)
    report = db.get(Report, report_id)
    if report is None or report.project_id != project_id:
        raise ValueError("report does not belong to project")

    context_hash = ctx_svc.compute_m35_context_hash(
        db,
        project_id=project_id,
        report_id=report_id,
        goal=goal,
        strategy=strategy,
        budget={},
    )
    job_payload = {
        "project_id": str(project_id),
        "report_id": str(report_id),
        "user_id": str(user_id),
        "goal": goal,
        "strategy": strategy,
        "payload": dict(payload or {}),
        "context_hash": context_hash,
        "m35_version": M35_VERSION,
        "force": bool(force),
    }
    settings = get_settings()
    enqueued = jobs_service.enqueue_job(
        db,
        job_type="orchestration_run",
        payload=job_payload,
        idempotency_key=(
            f"orchestration:{report_id}:{context_hash}:"
            f"{M35_VERSION}:{strategy}"
        ),
        report_id=report_id,
        user_id=user_id,
        max_attempts=int(settings.orchestration_job_max_attempts),
    )
    return enqueued.job.id


__all__ = ["enqueue_orchestration"]
