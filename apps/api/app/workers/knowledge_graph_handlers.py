"""M25 — Knowledge graph build worker handler."""
from __future__ import annotations

import logging
import time
import uuid

from app.core.config import get_settings
from app.db.models.project import Project
from app.db.session import SessionLocal
from app.services.knowledge_graph import builder as builder_svc
from app.services.knowledge_graph import context as ctx_svc

logger = logging.getLogger(__name__)


def _parse_uuid(value) -> uuid.UUID | None:
    if value is None:
        return None
    try:
        return uuid.UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        return None


def handle_knowledge_graph_build(ctx) -> dict:
    payload = ctx.payload or {}
    project_id_raw = payload.get("project_id")
    if not project_id_raw:
        raise ValueError("knowledge_graph payload missing project_id")
    project_id = _parse_uuid(project_id_raw)
    if project_id is None:
        raise ValueError("knowledge_graph project_id invalid")

    user_id = _parse_uuid(payload.get("user_id"))
    force = bool(payload.get("force", False))
    payload_context = payload.get("context_hash")

    settings = get_settings()
    if not settings.knowledge_graph_enabled:
        return {"status": "disabled"}

    with SessionLocal() as db:
        if user_id is None:
            project = db.get(Project, project_id)
            if project is None:
                raise ValueError("knowledge_graph project not found")
            user_id = project.user_id

        if payload_context:
            current_context = ctx_svc.compute_graph_context_hash(
                db, project_id=project_id
            )
            if current_context != payload_context:
                logger.info(
                    "knowledge_graph_stale_context project_id=%s",
                    project_id,
                )
                builder_svc.record_skipped_run(
                    db,
                    project_id=project_id,
                    user_id=user_id,
                    context_hash=payload_context,
                    graph_version_id=None,
                    reason="stale_context",
                    duration_ms=0,
                )
                db.commit()
                return {
                    "status": "skipped",
                    "reason": "stale_context",
                    "payload_context": payload_context,
                    "current_context": current_context,
                }

        started = time.perf_counter()
        result = builder_svc.build_knowledge_graph(
            db,
            user_id=user_id,
            project_id=project_id,
            force=force,
            commit=True,
        )
        return {
            "status": result.run.status,
            "skipped": result.skipped,
            "node_count": result.node_count,
            "edge_count": result.edge_count,
            "graph_version_id": (
                str(result.graph_version.id)
                if result.graph_version else None
            ),
            "duration_ms": int((time.perf_counter() - started) * 1000),
        }


__all__ = ["handle_knowledge_graph_build"]
