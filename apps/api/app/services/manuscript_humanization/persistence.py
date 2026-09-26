"""M32 — Idempotent persistence with durable failure audit.

Reuses M14 HumanizationRun with stage='manuscript'.

Idempotency contract:
  - A completed run for the same
    (manuscript_version_id, context_hash, m32_version, mode) is reused.
  - The reused run is returned as-is; no synthetic "skipped" row is
    inserted (M14 status CHECK does not include "skipped").
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import (
    ManuscriptHumanizationConfigurationInvalid,
    ManuscriptHumanizationInvalid,
)
from app.db.models.humanization import HumanizationRun
from app.db.models.manuscript import Manuscript, ManuscriptVersion
from app.db.models.report import Report
from app.db.session import SessionLocal
from app.domain.humanization_m32 import (
    M32_STAGE,
    M32_VERSION,
)
from app.services.manuscript_humanization import context as ctx_svc
from app.services.manuscript_humanization import engine as engine_svc

logger = logging.getLogger(__name__)


@dataclass
class PersistedM32Result:
    run: HumanizationRun
    skipped: bool


def _lock_report(db: Session, *, report_id: uuid.UUID) -> None:
    db.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:k))"),
        {"k": f"manuscript_humanization:{report_id}"},
    )


def _completed_run(
    db: Session,
    *,
    manuscript_version_id: uuid.UUID,
    context_hash: str,
    mode: str,
) -> HumanizationRun | None:
    return db.execute(
        select(HumanizationRun).where(
            HumanizationRun.stage == M32_STAGE,
            HumanizationRun.manuscript_version_id
            == manuscript_version_id,
            HumanizationRun.context_hash == context_hash,
            HumanizationRun.m32_version == M32_VERSION,
            HumanizationRun.mode == mode,
            HumanizationRun.status == "success",
        )
    ).scalar_one_or_none()


def _persist_failed_run(
    *,
    report_id: uuid.UUID,
    manuscript_id: uuid.UUID | None,
    manuscript_version_id: uuid.UUID,
    context_hash: str | None,
    mode: str,
    error_message: str,
    duration_ms: int,
    language: str,
) -> None:
    try:
        with SessionLocal() as s:
            now = datetime.now(UTC)
            s.add(HumanizationRun(
                report_id=report_id,
                stage=M32_STAGE,
                language=language,
                policy_json={
                    "mode": mode,
                    "error_message": error_message[:500],
                    "duration_ms": int(duration_ms),
                },
                status="failed",
                manuscript_id=manuscript_id,
                manuscript_version_id=manuscript_version_id,
                mode=mode,
                m32_version=M32_VERSION,
                context_hash=context_hash or "-",
                completed_at=now,
            ))
            s.commit()
    except Exception:
        logger.exception("m32_failed_run_audit_failed")


def run_m32_persisted(
    db: Session,
    *,
    report_id: uuid.UUID,
    manuscript_version_id: uuid.UUID,
    mode: str,
    force: bool = False,
    commit: bool = True,
) -> PersistedM32Result:
    settings = get_settings()
    if not settings.manuscript_humanization_enabled:
        raise ManuscriptHumanizationConfigurationInvalid(
            "manuscript humanization is disabled"
        )

    report = db.get(Report, report_id)
    if report is None or report.project_id is None:
        raise ManuscriptHumanizationInvalid("report has no project")
    version = db.get(ManuscriptVersion, manuscript_version_id)
    if version is None:
        raise ManuscriptHumanizationInvalid("manuscript version not found")
    manuscript = db.get(Manuscript, version.manuscript_id)
    if manuscript is None or manuscript.report_id != report_id:
        raise ManuscriptHumanizationInvalid("manuscript mismatch")

    started = datetime.now(UTC)
    context_hash: str | None = None

    try:
        _lock_report(db, report_id=report_id)

        context_hash = ctx_svc.compute_m32_context_hash(
            db,
            manuscript_version_id=manuscript_version_id,
            mode=mode,
        )

        existing = _completed_run(
            db,
            manuscript_version_id=manuscript_version_id,
            context_hash=context_hash,
            mode=mode,
        )
        if existing is not None:
            # Idempotent reuse: no new row is inserted. This avoids
            # violating the partial unique index
            # ``ux_humanization_runs_m32_completed`` (which covers
            # status='success' for M32 rows).
            return PersistedM32Result(run=existing, skipped=True)

        run = HumanizationRun(
            report_id=report_id,
            stage=M32_STAGE,
            language=report.output_language,
            policy_json={"mode": mode},
            status="running",
            manuscript_id=manuscript.id,
            manuscript_version_id=manuscript_version_id,
            mode=mode,
            m32_version=M32_VERSION,
            context_hash=context_hash,
            cost_usd=Decimal("0"),
            tokens_used=0,
        )
        db.add(run)
        db.flush()

        result = engine_svc.run_manuscript_humanization(
            db,
            project_id=report.project_id,
            report_id=report_id,
            manuscript_id=manuscript.id,
            manuscript_version_id=manuscript_version_id,
            mode=mode,
            context_hash=context_hash,
        )

        now = datetime.now(UTC)
        run.status = "success"
        run.gate = result.gate
        run.preservation_summary = {
            "prose_available": result.prose_available,
            "iterations": result.iterations,
            "preservation_ratio": result.preservation_ratio,
            "mode": result.mode,
        }
        run.completed_at = now
        # M14 model has no duration_ms column; keep the value in
        # policy_json (which is schema-free JSONB).
        run.policy_json = {
            "mode": mode,
            "duration_ms": int(result.duration_ms),
            "warnings": list(result.warnings),
        }

        if commit:
            db.commit()
            db.refresh(run)
        else:
            db.flush()
        return PersistedM32Result(run=run, skipped=False)

    except Exception as exc:
        logger.exception("manuscript_humanization_persist_failed")
        if commit:
            try:
                db.rollback()
            except Exception:
                logger.exception("m32_rollback_failed")
        duration_ms = int(
            (datetime.now(UTC) - started).total_seconds() * 1000
        )
        _persist_failed_run(
            report_id=report_id,
            manuscript_id=manuscript.id if manuscript else None,
            manuscript_version_id=manuscript_version_id,
            context_hash=context_hash,
            mode=mode,
            error_message=str(exc),
            duration_ms=duration_ms,
            language=report.output_language if report else "en",
        )
        raise


__all__ = ["PersistedM32Result", "run_m32_persisted"]
