"""M21 — Worker handler for research_classification."""
from __future__ import annotations

import logging
import uuid

from app.db.models.project import Project
from app.db.session import SessionLocal
from app.domain.jobs import JobContext
from app.services.classification.orchestrator import classify_project

logger = logging.getLogger(__name__)


def handle_research_classification(ctx: JobContext) -> None:
    raw = ctx.payload.get("project_id")
    if not raw:
        raise ValueError(
            "research_classification payload missing project_id"
        )
    project_id = uuid.UUID(str(raw))

    with SessionLocal() as db:
        project = db.get(Project, project_id)
        if project is None:
            return
        if project.status == "archived":
            return
        classify_project(
            db, project_id=project_id, user_id=None, commit=True
        )
