"""M35 — Deterministic context hash.

Includes goal, budget, planner version, target profile if present.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.manuscript import Manuscript, ManuscriptVersion
from app.db.models.publication import (
    PublicationComplianceRun,
    PublicationTargetSelection,
)
from app.db.models.report import Report
from app.domain.orchestration import (
    M35_VERSION,
    ORCHESTRATION_PLANNER_VERSION,
    ORCHESTRATION_TOOL_REGISTRY_VERSION,
)


def _current_version_fingerprint(
    db: Session, *, report_id: uuid.UUID,
) -> dict[str, Any] | None:
    ms = db.execute(
        select(Manuscript).where(Manuscript.report_id == report_id)
    ).scalar_one_or_none()
    if ms is None or ms.current_version_id is None:
        return None
    version = db.get(ManuscriptVersion, ms.current_version_id)
    if version is None:
        return None
    return {
        "manuscript_id": str(ms.id),
        "version_id": str(version.id),
        "version_number": int(version.version),
        "context_hash": version.context_hash,
    }


def _target_selection_fingerprint(
    db: Session, *, report_id: uuid.UUID,
) -> dict[str, Any] | None:
    sel = db.execute(
        select(PublicationTargetSelection)
        .where(PublicationTargetSelection.report_id == report_id)
        .order_by(
            PublicationTargetSelection.created_at.desc(),
            PublicationTargetSelection.id.desc(),
        )
        .limit(1)
    ).scalar_one_or_none()
    if sel is None:
        return None
    return {"target_id": str(sel.target_id)}


def _latest_compliance_fingerprint(
    db: Session, *, report_id: uuid.UUID,
) -> dict[str, Any] | None:
    run = db.execute(
        select(PublicationComplianceRun)
        .where(
            PublicationComplianceRun.report_id == report_id,
            PublicationComplianceRun.status == "completed",
        )
        .order_by(
            PublicationComplianceRun.created_at.desc(),
            PublicationComplianceRun.id.desc(),
        )
        .limit(1)
    ).scalar_one_or_none()
    if run is None:
        return None
    return {
        "run_id": str(run.id),
        "target_id": str(run.target_id),
        "context_hash": run.context_hash,
    }


def compute_m35_context_hash(
    db: Session,
    *,
    project_id: uuid.UUID,
    report_id: uuid.UUID,
    goal: str,
    strategy: str,
    budget: dict,
) -> str:
    report = db.get(Report, report_id)
    if report is None or report.project_id != project_id:
        return hashlib.sha256(b"missing-report").hexdigest()

    version_fp = _current_version_fingerprint(
        db, report_id=report_id,
    )
    target_fp = _target_selection_fingerprint(
        db, report_id=report_id,
    )
    compliance_fp = _latest_compliance_fingerprint(
        db, report_id=report_id,
    )

    payload: dict[str, Any] = {
        "m35_version": M35_VERSION,
        "planner_version": ORCHESTRATION_PLANNER_VERSION,
        "tool_registry_version": ORCHESTRATION_TOOL_REGISTRY_VERSION,
        "project_id": str(project_id),
        "report_id": str(report_id),
        "goal": goal,
        "strategy": strategy,
        "budget": budget,
        "current_manuscript": version_fp,
        "target_selection": target_fp,
        "latest_compliance": compliance_fp,
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def compute_node_context_hash(
    *,
    run_context_hash: str,
    node_key: str,
    node_version: str,
    payload: dict,
) -> str:
    blob = json.dumps(
        {
            "run_context_hash": run_context_hash,
            "node_key": node_key,
            "node_version": node_version,
            "payload": payload,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


__all__ = ["compute_m35_context_hash", "compute_node_context_hash"]
