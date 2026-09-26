"""M33 — Deterministic orchestrator. No persistence."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import (
    PublicationComplianceConfigurationInvalid,
)
from app.domain.publication import (
    COMPLIANCE_RULES_VERSION,
    M33_VERSION,
    ComplianceGate,
    ComplianceSeverity,
    compute_gate,
)
from app.services.publication.findings import ComplianceFinding
from app.services.publication.rules import (
    build_checklist_state,
    build_snapshot,
    run_all_rules,
)


@dataclass
class M33Result:
    project_id: uuid.UUID
    report_id: uuid.UUID
    manuscript_id: uuid.UUID
    manuscript_version_id: uuid.UUID
    target_id: uuid.UUID
    target_profile_version: str
    context_hash: str
    findings: list[ComplianceFinding] = field(default_factory=list)
    gate: str = ComplianceGate.PASS.value
    checklist_state: dict = field(default_factory=dict)
    formatting_summary: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    duration_ms: int = 0


def run_publication_compliance(
    db: Session,
    *,
    project_id: uuid.UUID,
    report_id: uuid.UUID,
    manuscript_id: uuid.UUID,
    manuscript_version_id: uuid.UUID,
    target_id: uuid.UUID,
    context_hash: str,
) -> M33Result:
    started = time.perf_counter()
    settings = get_settings()
    if not settings.publication_targets_enabled:
        raise PublicationComplianceConfigurationInvalid(
            "publication targets are disabled"
        )

    snap = build_snapshot(
        db,
        project_id=project_id,
        report_id=report_id,
        manuscript_id=manuscript_id,
        manuscript_version_id=manuscript_version_id,
        target_id=target_id,
    )
    findings = run_all_rules(snap)
    max_findings = int(settings.publication_compliance_max_findings)
    warnings: list[str] = []
    if len(findings) > max_findings:
        warnings.append(
            f"findings_truncated:{len(findings)}->{max_findings}"
        )
        findings = findings[:max_findings]

    blocking = sum(
        1 for f in findings if f.severity == ComplianceSeverity.BLOCKING.value
    )
    errors = sum(
        1 for f in findings if f.severity == ComplianceSeverity.ERROR.value
    )
    warns = sum(
        1 for f in findings if f.severity == ComplianceSeverity.WARNING.value
    )
    gate = compute_gate(
        blocking_count=blocking,
        error_count=errors,
        warning_count=warns,
    )

    checklist_state = build_checklist_state(snap.target, findings)
    formatting_summary = {
        "citation_style": snap.target.citation_style,
        "venue": snap.target.venue,
        "venue_type": snap.target.venue_type,
        "profile_version": snap.target.profile_version,
    }

    return M33Result(
        project_id=project_id,
        report_id=report_id,
        manuscript_id=manuscript_id,
        manuscript_version_id=manuscript_version_id,
        target_id=target_id,
        target_profile_version=snap.target.profile_version,
        context_hash=context_hash,
        findings=findings,
        gate=gate,
        checklist_state=checklist_state,
        formatting_summary=formatting_summary,
        warnings=warnings,
        duration_ms=int((time.perf_counter() - started) * 1000),
    )


_ = M33_VERSION, COMPLIANCE_RULES_VERSION  # documented

__all__ = ["M33Result", "run_publication_compliance"]
