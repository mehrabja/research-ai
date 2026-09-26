"""M31 — Idempotent persistence with durable failure audit."""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import (
    AcademicQAConfigurationInvalid,
    AcademicQAInvalid,
)
from app.db.models.academic_qa import (
    AcademicQAFinding,
    AcademicQARun,
)
from app.db.models.manuscript import Manuscript, ManuscriptVersion
from app.db.models.report import Report
from app.db.session import SessionLocal
from app.domain.academic_qa import (
    M31_VERSION,
    QA_RULES_VERSION,
    QASeverity,
    QAStatus,
)
from app.services.academic_qa import context as ctx_svc
from app.services.academic_qa import engine as engine_svc
from app.services.academic_qa import validation as val_svc

logger = logging.getLogger(__name__)


@dataclass
class PersistedM31Result:
    run: AcademicQARun
    skipped: bool


def _lock_report(db: Session, *, report_id: uuid.UUID) -> None:
    db.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:k))"),
        {"k": f"academic_qa:{report_id}"},
    )


def _completed_run(
    db: Session,
    *,
    report_id: uuid.UUID,
    manuscript_version_id: uuid.UUID,
    context_hash: str,
) -> AcademicQARun | None:
    return db.execute(
        select(AcademicQARun).where(
            AcademicQARun.report_id == report_id,
            AcademicQARun.manuscript_version_id == manuscript_version_id,
            AcademicQARun.context_hash == context_hash,
            AcademicQARun.m31_version == M31_VERSION,
            AcademicQARun.rules_version == QA_RULES_VERSION,
            AcademicQARun.status == QAStatus.COMPLETED.value,
        )
    ).scalar_one_or_none()


def _persist_failed_run(
    *,
    project_id: uuid.UUID,
    report_id: uuid.UUID,
    manuscript_id: uuid.UUID | None,
    manuscript_version_id: uuid.UUID,
    context_hash: str | None,
    error_message: str,
    duration_ms: int,
) -> None:
    try:
        with SessionLocal() as s:
            now = datetime.now(UTC)
            s.add(AcademicQARun(
                project_id=project_id,
                report_id=report_id,
                manuscript_id=manuscript_id,
                manuscript_version_id=manuscript_version_id,
                context_hash=context_hash or "-",
                m31_version=M31_VERSION,
                rules_version=QA_RULES_VERSION,
                status=QAStatus.FAILED.value,
                execution_mode="deterministic",
                error_message=error_message[:500],
                duration_ms=int(duration_ms),
                completed_at=now,
            ))
            s.commit()
    except Exception:
        logger.exception("m31_failed_run_audit_failed")


def run_m31_persisted(
    db: Session,
    *,
    report_id: uuid.UUID,
    manuscript_version_id: uuid.UUID,
    force: bool = False,
    commit: bool = True,
) -> PersistedM31Result:
    settings = get_settings()
    if not settings.academic_qa_enabled:
        raise AcademicQAConfigurationInvalid("academic QA is disabled")

    report = db.get(Report, report_id)
    if report is None or report.project_id is None:
        raise AcademicQAInvalid("report has no project")
    version = db.get(ManuscriptVersion, manuscript_version_id)
    if version is None:
        raise AcademicQAInvalid("manuscript version not found")
    manuscript = db.get(Manuscript, version.manuscript_id)
    if manuscript is None or manuscript.report_id != report_id:
        raise AcademicQAInvalid("manuscript mismatch")

    started = datetime.now(UTC)
    context_hash: str | None = None

    try:
        _lock_report(db, report_id=report_id)

        context_hash = ctx_svc.compute_m31_context_hash(
            db, manuscript_version_id=manuscript_version_id,
        )

        existing = _completed_run(
            db,
            report_id=report_id,
            manuscript_version_id=manuscript_version_id,
            context_hash=context_hash,
        )
        if existing is not None:
            now = datetime.now(UTC)
            skipped = AcademicQARun(
                project_id=report.project_id,
                report_id=report_id,
                manuscript_id=manuscript.id,
                manuscript_version_id=manuscript_version_id,
                context_hash=context_hash,
                m31_version=M31_VERSION,
                rules_version=QA_RULES_VERSION,
                status=QAStatus.SKIPPED.value,
                execution_mode=existing.execution_mode,
                finding_count=existing.finding_count,
                blocking_count=existing.blocking_count,
                error_count=existing.error_count,
                warning_count=existing.warning_count,
                info_count=existing.info_count,
                gate=existing.gate,
                dimension_scores=existing.dimension_scores,
                summary=existing.summary,
                warnings=["reused_previous_completed_run"],
                duration_ms=0,
                completed_at=now,
            )
            db.add(skipped)
            if commit:
                db.commit()
                db.refresh(skipped)
            else:
                db.flush()
            return PersistedM31Result(run=skipped, skipped=True)

        run = AcademicQARun(
            project_id=report.project_id,
            report_id=report_id,
            manuscript_id=manuscript.id,
            manuscript_version_id=manuscript_version_id,
            context_hash=context_hash,
            m31_version=M31_VERSION,
            rules_version=QA_RULES_VERSION,
            status=QAStatus.RUNNING.value,
            execution_mode="deterministic",
            finding_count=0,
            blocking_count=0,
            error_count=0,
            warning_count=0,
            info_count=0,
        )
        db.add(run)
        db.flush()

        result = engine_svc.run_academic_qa(
            db,
            project_id=report.project_id,
            report_id=report_id,
            manuscript_id=manuscript.id,
            manuscript_version_id=manuscript_version_id,
            context_hash=context_hash,
        )

        validation = val_svc.validate_findings(result.findings)
        if validation.status == "invalid":
            raise AcademicQAInvalid(
                "invalid findings: " + ";".join(validation.errors[:5])
            )

        counts = {
            QASeverity.INFO.value: 0,
            QASeverity.WARNING.value: 0,
            QASeverity.ERROR.value: 0,
            QASeverity.BLOCKING.value: 0,
        }
        for f in result.findings:
            if f.severity in counts:
                counts[f.severity] += 1
            db.add(AcademicQAFinding(
                qa_run_id=run.id,
                project_id=report.project_id,
                report_id=report_id,
                manuscript_version_id=manuscript_version_id,
                manuscript_section_id=f.manuscript_section_id,
                claim_id=f.claim_id,
                citation_id=f.citation_id,
                rule_id=f.rule_id,
                category=f.category,
                severity=f.severity,
                title=f.title,
                message=f.message,
                location=f.location,
                evidence=f.evidence,
                classification=f.classification,
                confidence=f.confidence,
                status="open",
                remediation=f.remediation,
                finding_meta=f.meta,
            ))

        now = datetime.now(UTC)
        run.status = QAStatus.COMPLETED.value
        run.finding_count = len(result.findings)
        run.blocking_count = counts[QASeverity.BLOCKING.value]
        run.error_count = counts[QASeverity.ERROR.value]
        run.warning_count = counts[QASeverity.WARNING.value]
        run.info_count = counts[QASeverity.INFO.value]
        run.gate = result.gate
        run.dimension_scores = result.dimension_scores
        run.summary = {
            "composite_score": result.composite_score,
            "gate": result.gate,
            "execution_mode": result.execution_mode,
        }
        run.warnings = list(result.warnings) + list(validation.warnings)
        run.duration_ms = int(result.duration_ms)
        run.completed_at = now

        if commit:
            db.commit()
            db.refresh(run)
        else:
            db.flush()
        return PersistedM31Result(run=run, skipped=False)

    except Exception as exc:
        logger.exception("academic_qa_persist_failed")
        if commit:
            try:
                db.rollback()
            except Exception:
                logger.exception("m31_rollback_failed")
        duration_ms = int(
            (datetime.now(UTC) - started).total_seconds() * 1000
        )
        _persist_failed_run(
            project_id=report.project_id,
            report_id=report_id,
            manuscript_id=manuscript.id if manuscript else None,
            manuscript_version_id=manuscript_version_id,
            context_hash=context_hash,
            error_message=str(exc),
            duration_ms=duration_ms,
        )
        raise


__all__ = ["PersistedM31Result", "run_m31_persisted"]
