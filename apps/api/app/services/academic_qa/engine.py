"""M31 — Orchestrator. No persistence."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import AcademicQAConfigurationInvalid
from app.domain.academic_qa import (
    QAExecutionMode,
    QASeverity,
    compute_gate,
)
from app.services.academic_qa.findings import QAFinding
from app.services.academic_qa.rules import build_snapshot, run_all_rules
from app.services.academic_qa.scoring import (
    compute_composite,
    compute_dimension_scores,
)


@dataclass
class M31Result:
    project_id: uuid.UUID
    report_id: uuid.UUID
    manuscript_id: uuid.UUID
    manuscript_version_id: uuid.UUID
    context_hash: str
    execution_mode: str
    findings: list[QAFinding] = field(default_factory=list)
    gate: str = "pass"
    dimension_scores: dict = field(default_factory=dict)
    composite_score: float = 0.0
    warnings: list[str] = field(default_factory=list)
    duration_ms: int = 0


def run_academic_qa(
    db: Session,
    *,
    project_id: uuid.UUID,
    report_id: uuid.UUID,
    manuscript_id: uuid.UUID,
    manuscript_version_id: uuid.UUID,
    context_hash: str,
) -> M31Result:
    started = time.perf_counter()
    settings = get_settings()
    if not settings.academic_qa_enabled:
        raise AcademicQAConfigurationInvalid("academic QA is disabled")

    snap = build_snapshot(
        db,
        manuscript_id=manuscript_id,
        manuscript_version_id=manuscript_version_id,
        project_id=project_id,
        report_id=report_id,
    )
    findings = run_all_rules(snap)
    max_findings = int(settings.academic_qa_max_findings)
    warnings: list[str] = []
    if len(findings) > max_findings:
        warnings.append(f"findings_truncated:{len(findings)}->{max_findings}")
        findings = findings[:max_findings]

    dim_scores = compute_dimension_scores(findings)
    composite = compute_composite(dim_scores)

    blocking = sum(
        1 for f in findings if f.severity == QASeverity.BLOCKING.value
    )
    errors = sum(
        1 for f in findings if f.severity == QASeverity.ERROR.value
    )
    warn = sum(
        1 for f in findings if f.severity == QASeverity.WARNING.value
    )
    gate = compute_gate(
        blocking_count=blocking,
        error_count=errors,
        warning_count=warn,
    )

    return M31Result(
        project_id=project_id,
        report_id=report_id,
        manuscript_id=manuscript_id,
        manuscript_version_id=manuscript_version_id,
        context_hash=context_hash,
        execution_mode=QAExecutionMode.DETERMINISTIC.value,
        findings=findings,
        gate=gate,
        dimension_scores=dim_scores,
        composite_score=composite,
        warnings=warnings,
        duration_ms=int((time.perf_counter() - started) * 1000),
    )


__all__ = ["M31Result", "run_academic_qa"]
