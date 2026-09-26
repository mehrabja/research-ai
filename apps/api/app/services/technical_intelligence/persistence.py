"""M29 — Idempotent persistence with durable failure audit."""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import (
    TechnicalIntelligenceConfigurationInvalid,
    TechnicalIntelligenceProvenanceMissing,
)
from app.db.models.experiment_result import ExperimentResult
from app.db.models.metric import Metric
from app.db.models.technical_fact import TechnicalFact
from app.db.models.technical_intelligence import TechnicalIntelligenceRun
from app.db.session import SessionLocal
from app.domain.technical_intelligence import (
    M29_VERSION,
    TechnicalIntelligenceRunStatus,
)
from app.services.technical_intelligence import context as ctx_svc
from app.services.technical_intelligence import engine as engine_svc
from app.services.technical_intelligence import linking as link_svc

logger = logging.getLogger(__name__)


@dataclass
class PersistedM29Result:
    run: TechnicalIntelligenceRun
    skipped: bool


def _lock_project(db: Session, *, project_id: uuid.UUID) -> None:
    db.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:k))"),
        {"k": f"technical_intelligence:{project_id}"},
    )


def _completed_run(
    db: Session, *, project_id: uuid.UUID, context_hash: str,
) -> TechnicalIntelligenceRun | None:
    return db.execute(
        select(TechnicalIntelligenceRun).where(
            TechnicalIntelligenceRun.project_id == project_id,
            TechnicalIntelligenceRun.context_hash == context_hash,
            TechnicalIntelligenceRun.m29_version == M29_VERSION,
            TechnicalIntelligenceRun.status == "completed",
        )
    ).scalar_one_or_none()


def _persist_failed_run(
    *,
    project_id: uuid.UUID,
    report_id: uuid.UUID | None,
    context_hash: str | None,
    error_message: str,
    duration_ms: int,
) -> None:
    try:
        with SessionLocal() as s:
            now = datetime.now(UTC)
            s.add(TechnicalIntelligenceRun(
                project_id=project_id,
                report_id=report_id,
                context_hash=context_hash or "-",
                m29_version=M29_VERSION,
                status=TechnicalIntelligenceRunStatus.FAILED.value,
                error_message=error_message[:500],
                duration_ms=int(duration_ms),
                completed_at=now,
            ))
            s.commit()
    except Exception:
        logger.exception("m29_failed_run_audit_failed")


def run_m29_persisted(
    db: Session,
    *,
    project_id: uuid.UUID,
    report_id: uuid.UUID | None = None,
    manuscript_version_id: uuid.UUID | None = None,
    force: bool = False,
    commit: bool = True,
) -> PersistedM29Result:
    settings = get_settings()
    if not settings.technical_intelligence_enabled:
        raise TechnicalIntelligenceConfigurationInvalid(
            "technical intelligence is disabled"
        )

    context_hash: str | None = None
    started = datetime.now(UTC)

    try:
        _lock_project(db, project_id=project_id)

        context_hash = ctx_svc.compute_m29_context_hash(
            db, project_id=project_id
        )

        existing = _completed_run(
            db, project_id=project_id, context_hash=context_hash,
        )
        if existing is not None:
            now = datetime.now(UTC)
            skipped = TechnicalIntelligenceRun(
                project_id=project_id, report_id=report_id,
                context_hash=context_hash, m29_version=M29_VERSION,
                status=TechnicalIntelligenceRunStatus.SKIPPED.value,
                fact_count=existing.fact_count,
                result_count=existing.result_count,
                metric_count=existing.metric_count,
                warnings=["reused_previous_completed_run"],
                duration_ms=0, completed_at=now,
            )
            db.add(skipped)
            if commit:
                db.commit()
                db.refresh(skipped)
            else:
                db.flush()
            return PersistedM29Result(run=skipped, skipped=True)

        run = TechnicalIntelligenceRun(
            project_id=project_id, report_id=report_id,
            context_hash=context_hash, m29_version=M29_VERSION,
            status=TechnicalIntelligenceRunStatus.RUNNING.value,
            fact_count=0, result_count=0, metric_count=0,
        )
        db.add(run)
        db.flush()

        result = engine_svc.run_technical_intelligence(
            db,
            project_id=project_id,
            report_id=report_id,
            manuscript_version_id=manuscript_version_id,
            context_hash=context_hash,
        )

        for f in result.facts:
            if not f.provenance:
                raise TechnicalIntelligenceProvenanceMissing(
                    "fact missing provenance"
                )
            db.add(TechnicalFact(
                technical_intelligence_run_id=run.id,
                project_id=f.project_id,
                report_id=f.report_id,
                manuscript_version_id=f.manuscript_version_id,
                project_file_id=f.project_file_id,
                code_analysis_id=f.code_analysis_id,
                data_profile_id=f.data_profile_id,
                fact_type=f.fact_type,
                fact_key=f.fact_key, fact_value=f.fact_value,
                normalized_value=f.normalized_value, unit=f.unit,
                confidence=f.confidence, provenance=f.provenance,
                context_hash=context_hash, status=f.status,
            ))
        db.flush()

        algorithm_index = link_svc.build_algorithm_index(
            db, run_id=run.id,
        )

        metric_total = 0
        for r in result.results:
            if not r.provenance:
                raise TechnicalIntelligenceProvenanceMissing(
                    "result missing provenance"
                )
            if "artifact_id" not in r.provenance:
                raise TechnicalIntelligenceProvenanceMissing(
                    "result provenance missing artifact_id"
                )
            link_fact_id = link_svc.link_experiment_to_algorithm(
                algorithm_index=algorithm_index,
                experiment_key=r.experiment_key,
                value_row=r.value,
            )
            exp = ExperimentResult(
                technical_intelligence_run_id=run.id,
                project_id=project_id, report_id=report_id,
                manuscript_version_id=manuscript_version_id,
                technical_fact_id=link_fact_id,
                project_file_id=uuid.UUID(
                    r.provenance["artifact_id"]
                ),
                result_type=r.result_type, name=r.name,
                description=None, value=r.value, unit=None,
                experiment_key=r.experiment_key,
                provenance=r.provenance, context_hash=context_hash,
                status="parsed",
            )
            db.add(exp)
            db.flush()
            for m in r.metrics:
                if metric_total >= int(
                    settings.technical_intelligence_max_metrics
                ):
                    break
                db.add(Metric(
                    technical_intelligence_run_id=run.id,
                    project_id=project_id,
                    experiment_result_id=exp.id,
                    name=m.name, normalized_name=m.normalized_name,
                    value_numeric=m.value_numeric,
                    value_text=m.value_text, unit=m.unit,
                    split=m.split, direction=m.direction,
                    baseline_value=None, delta_value=None,
                    is_primary=False, provenance=m.provenance,
                    context_hash=context_hash, status="parsed",
                ))
                metric_total += 1

        now = datetime.now(UTC)
        run.status = TechnicalIntelligenceRunStatus.COMPLETED.value
        run.fact_count = len(result.facts)
        run.result_count = len(result.results)
        run.metric_count = metric_total
        run.input_snapshot = {
            "project_id": str(project_id),
            "report_id": str(report_id) if report_id else None,
            "manuscript_version_id": (
                str(manuscript_version_id)
                if manuscript_version_id else None
            ),
        }
        run.output_summary = {
            "fact_count": len(result.facts),
            "result_count": len(result.results),
            "metric_count": metric_total,
            "m29_version": M29_VERSION,
        }
        run.warnings = list(result.warnings)
        run.error_message = None
        run.duration_ms = int(result.duration_ms)
        run.completed_at = now

        if commit:
            db.commit()
            db.refresh(run)
        else:
            db.flush()
        return PersistedM29Result(run=run, skipped=False)

    except Exception as exc:
        logger.exception("technical_intelligence_persist_failed")
        if commit:
            try:
                db.rollback()
            except Exception:
                logger.exception("m29_rollback_failed")
        duration_ms = int(
            (datetime.now(UTC) - started).total_seconds() * 1000
        )
        _persist_failed_run(
            project_id=project_id, report_id=report_id,
            context_hash=context_hash,
            error_message=str(exc), duration_ms=duration_ms,
        )
        raise


__all__ = ["PersistedM29Result", "run_m29_persisted"]
