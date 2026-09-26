"""M27 — Enqueue helper for manuscript generation."""
from __future__ import annotations

import logging
import uuid

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import (
    ManuscriptGenerationFailed,
    ManuscriptResearchPlanMissing,
)
from app.domain.manuscript import MANUSCRIPT_ARCHITECTURE_VERSION
from app.services import jobs as jobs_service
from app.services.manuscript import context as ctx_svc
from app.services.projects import get_project
from app.services.reports import get_report

logger = logging.getLogger(__name__)


def enqueue_manuscript_generate(
    db: Session,
    *,
    report_id: uuid.UUID,
    user_id: uuid.UUID,
    force: bool = False,
) -> uuid.UUID:
    report = get_report(db, user_id=user_id, report_id=report_id)
    if report.project_id is None:
        raise ManuscriptGenerationFailed("report has no project")
    project = get_project(
        db, user_id=user_id, project_id=report.project_id
    )
    if project.status == "archived":
        raise ManuscriptGenerationFailed("project is archived")

    plan = ctx_svc.resolve_ready_plan(db, project_id=project.id)
    if plan is None:
        raise ManuscriptResearchPlanMissing()

    context_hash = ctx_svc.compute_manuscript_context_hash(
        db, report=report, project=project, plan=plan
    )

    payload = {
        "report_id": str(report_id),
        "user_id": str(user_id),
        "context_hash": context_hash,
        "architecture_version": MANUSCRIPT_ARCHITECTURE_VERSION,
        "force": bool(force),
    }
    enqueued = jobs_service.enqueue_job(
        db,
        job_type="manuscript_generate",
        payload=payload,
        idempotency_key=(
            f"manuscript_generate:{report_id}:"
            f"{context_hash}:{MANUSCRIPT_ARCHITECTURE_VERSION}:"
            f"{int(force)}"
        ),
        report_id=report_id,
        user_id=user_id,
        max_attempts=getattr(
            get_settings(), "manuscript_job_max_attempts", 3
        ),
    )
    return enqueued.job.id


__all__ = ["enqueue_manuscript_generate"]
