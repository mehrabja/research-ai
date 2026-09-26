"""M33 — Idempotent persistence with durable failure audit."""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import (
    PublicationComplianceConfigurationInvalid,
    PublicationComplianceInvalid,
)
from app.db.models.manuscript import Manuscript, ManuscriptVersion
from app.db.models.publication import (
    PublicationComplianceFinding,
    PublicationComplianceRun,
    PublicationTarget,
)
from app.db.models.report import Report
from app.db.session import SessionLocal
from app.domain.publication import (
    COMPLIANCE_RULES_VERSION,
    M33_VERSION,
    ComplianceSeverity,
    ComplianceStatus,
)
from app.services.publication import context as ctx_svc
from app.services.publication import engine as engine_svc

logger = logging.getLogger(__name__)


@dataclass
class PersistedM33Result:
    run: PublicationComplianceRun
    skipped: bool


def _lock_report(db: Session, *, report_id: uuid.UUID) -> None:
    db.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:k))"),
        {"k": f"publication_compliance:{report_id}"},
    )


def _completed_run(
    db: Session,
    *,
    report_id: uuid.UUID,
    manuscript_version_id: uuid.UUID,
    target_id: uuid.UUID,
    context_hash: str,
) -> PublicationComplianceRun | None:
    return db.execute(
        select(PublicationComplianceRun).where(
            PublicationComplianceRun.report_id == report_id,
            PublicationComplianceRun.manuscript_version_id
            == manuscript_version_id,
            PublicationComplianceRun.target_id == target_id,
            PublicationComplianceRun.context_hash == context_hash,
            PublicationComplianceRun.m33_version == M33_VERSION,
            PublicationComplianceRun.rules_version
            == COMPLIANCE_RULES_VERSION,
            PublicationComplianceRun.status
            == ComplianceStatus.COMPLETED.value,
        )
    ).scalar_one_or_none()


def _persist_failed_run(
    *,
    project_id: uuid.UUID,
    report_id: uuid.UUID,
    manuscript_id: uuid.UUID | None,
    manuscript_version_id: uuid.UUID,
    target_id: uuid.UUID,
    target_profile_version: str,
    context_hash: str | None,
    error_message: str,
    duration_ms: int,
) -> None:
    try:
        with SessionLocal() as s:
            now = datetime.now(UTC)
            s.add(PublicationComplianceRun(
                project_id=project_id,
                report_id=report_id,
                manuscript_id=manuscript_id,
                manuscript_version_id=manuscript_version_id,
                target_id=target_id,
                context_hash=context_hash or "-",
                m33_version=M33_VERSION,
                rules_version=COMPLIANCE_RULES_VERSION,
                target_profile_version=target_profile_version,
                status=ComplianceStatus.FAILED.value,
                error_message=error_message[:500],
                duration_ms=int(duration_ms),
                completed_at=now,
            ))
            s.commit()
    except Exception:
        logger.exception("m33_failed_run_audit_failed")


def run_m33_persisted(
    db: Session,
    *,
    report_id: uuid.UUID,
    manuscript_version_id: uuid.UUID,
    target_id: uuid.UUID,
    force: bool = False,
    commit: bool = True,
) -> PersistedM33Result:
    settings = get_settings()
    if not settings.publication_targets_enabled:
        raise PublicationComplianceConfigurationInvalid(
            "publication targets are disabled"
        )

    report = db.get(Report, report_id)
    if report is None or report.project_id is None:
        raise PublicationComplianceInvalid("report has no project")
    version = db.get(ManuscriptVersion, manuscript_version_id)
    if version is None:
        raise PublicationComplianceInvalid("manuscript version not found")
    manuscript = db.get(Manuscript, version.manuscript_id)
    if manuscript is None or manuscript.report_id != report_id:
        raise PublicationComplianceInvalid("manuscript mismatch")
    target = db.get(PublicationTarget, target_id)
    if target is None or not target.active:
        raise PublicationComplianceInvalid(
            "target not found or inactive"
        )

    started = datetime.now(UTC)
    context_hash: str | None = None

    try:
        _lock_report(db, report_id=report_id)

        context_hash = ctx_svc.compute_m33_context_hash(
            db,
            manuscript_version_id=manuscript_version_id,
            target_id=target_id,
        )

        existing = _completed_run(
            db,
            report_id=report_id,
            manuscript_version_id=manuscript_version_id,
            target_id=target_id,
            context_hash=context_hash,
        )
        if existing is not None:
            return PersistedM33Result(run=existing, skipped=True)

        run = PublicationComplianceRun(
            project_id=report.project_id,
            report_id=report_id,
            manuscript_id=manuscript.id,
            manuscript_version_id=manuscript_version_id,
            target_id=target_id,
            context_hash=context_hash,
            m33_version=M33_VERSION,
            rules_version=COMPLIANCE_RULES_VERSION,
            target_profile_version=target.profile_version,
            status=ComplianceStatus.RUNNING.value,
            finding_count=0,
            blocking_count=0,
            error_count=0,
            warning_count=0,
            info_count=0,
        )
        db.add(run)
        db.flush()

        result = engine_svc.run_publication_compliance(
            db,
            project_id=report.project_id,
            report_id=report_id,
            manuscript_id=manuscript.id,
            manuscript_version_id=manuscript_version_id,
            target_id=target_id,
            context_hash=context_hash,
        )

        counts = {
            ComplianceSeverity.INFO.value: 0,
            ComplianceSeverity.WARNING.value: 0,
            ComplianceSeverity.ERROR.value: 0,
            ComplianceSeverity.BLOCKING.value: 0,
        }
        for f in result.findings:
            if f.severity in counts:
                counts[f.severity] += 1
            db.add(PublicationComplianceFinding(
                compliance_run_id=run.id,
                project_id=report.project_id,
                report_id=report_id,
                manuscript_version_id=manuscript_version_id,
                rule_id=f.rule_id,
                category=f.category,
                severity=f.severity,
                title=f.title,
                message=f.message,
                location=f.location,
                evidence=f.evidence,
                remediation=f.remediation,
                finding_meta=f.meta,
            ))

        now = datetime.now(UTC)
        run.status = ComplianceStatus.COMPLETED.value
        run.finding_count = len(result.findings)
        run.blocking_count = counts[ComplianceSeverity.BLOCKING.value]
        run.error_count = counts[ComplianceSeverity.ERROR.value]
        run.warning_count = counts[ComplianceSeverity.WARNING.value]
        run.info_count = counts[ComplianceSeverity.INFO.value]
        run.gate = result.gate
        run.checklist_state = result.checklist_state
        run.formatting_summary = result.formatting_summary
        run.warnings = list(result.warnings)
        run.duration_ms = int(result.duration_ms)
        run.completed_at = now

        if commit:
            db.commit()
            db.refresh(run)
        else:
            db.flush()
        return PersistedM33Result(run=run, skipped=False)

    except Exception as exc:
        logger.exception("publication_compliance_persist_failed")
        if commit:
            try:
                db.rollback()
            except Exception:
                logger.exception("m33_rollback_failed")
        duration_ms = int(
            (datetime.now(UTC) - started).total_seconds() * 1000
        )
        _persist_failed_run(
            project_id=report.project_id,
            report_id=report_id,
            manuscript_id=manuscript.id if manuscript else None,
            manuscript_version_id=manuscript_version_id,
            target_id=target_id,
            target_profile_version=target.profile_version,
            context_hash=context_hash,
            error_message=str(exc),
            duration_ms=duration_ms,
        )
        raise


__all__ = ["PersistedM33Result", "run_m33_persisted"]
