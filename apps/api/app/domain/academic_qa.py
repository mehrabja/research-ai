"""M31 — Academic QA domain primitives (pure)."""
from __future__ import annotations

from enum import StrEnum

M31_VERSION = "m31.1"
QA_RULES_VERSION = "m31-rules-v1"


class QACategory(StrEnum):
    CLAIM_QUALITY = "claim_quality"
    CITATION_INTEGRITY = "citation_integrity"
    EVIDENCE_COVERAGE = "evidence_coverage"
    METHODOLOGY = "methodology"
    NUMERICAL_CONSISTENCY = "numerical_consistency"
    STRUCTURAL_CONSISTENCY = "structural_consistency"
    TERMINOLOGY = "terminology"
    REPRODUCIBILITY = "reproducibility"
    ACADEMIC_STYLE = "academic_style"


class QASeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    BLOCKING = "blocking"


class QAGate(StrEnum):
    PASS = "pass"
    PASS_WITH_WARNINGS = "pass_with_warnings"
    BLOCKED = "blocked"


class QAStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class QAClassification(StrEnum):
    DETERMINISTIC = "deterministic"
    MODEL_ASSISTED = "model_assisted"
    HUMAN_CONFIRMED = "human_confirmed"


class QAExecutionMode(StrEnum):
    DETERMINISTIC = "deterministic"
    DETERMINISTIC_ADVISORY = "deterministic_advisory"


class QAFindingStatus(StrEnum):
    OPEN = "open"
    RESOLVED = "resolved"
    WAIVED = "waived"
    FALSE_POSITIVE = "false_positive"


QA_CATEGORIES = tuple(c.value for c in QACategory)
QA_SEVERITIES = tuple(s.value for s in QASeverity)
QA_GATES = tuple(g.value for g in QAGate)
QA_STATUSES = tuple(s.value for s in QAStatus)
QA_CLASSIFICATIONS = tuple(c.value for c in QAClassification)
QA_EXECUTION_MODES = tuple(m.value for m in QAExecutionMode)
QA_FINDING_STATUSES = tuple(s.value for s in QAFindingStatus)

# Dimension keys used in AcademicQARun.dimension_scores
QA_DIMENSIONS: tuple[str, ...] = (
    "citation_integrity",
    "evidence_coverage",
    "structural_integrity",
    "numerical_consistency",
    "methodology_completeness",
    "terminology_consistency",
    "reproducibility",
    "academic_style",
)

# Deterministic severity weighting for composite scoring.
# Blocking findings dominate. Info findings do not lower score.
SEVERITY_WEIGHTS: dict[str, float] = {
    QASeverity.INFO.value: 0.0,
    QASeverity.WARNING.value: 0.1,
    QASeverity.ERROR.value: 0.3,
    QASeverity.BLOCKING.value: 1.0,
}


def is_blocking_severity(severity: str) -> bool:
    return severity == QASeverity.BLOCKING.value


def compute_gate(
    *, blocking_count: int, error_count: int, warning_count: int,
) -> str:
    """Deterministic gate evaluation."""
    if blocking_count > 0:
        return QAGate.BLOCKED.value
    if error_count > 0 or warning_count > 0:
        return QAGate.PASS_WITH_WARNINGS.value
    return QAGate.PASS.value


__all__ = [
    "M31_VERSION",
    "QA_RULES_VERSION",
    "QACategory",
    "QASeverity",
    "QAGate",
    "QAStatus",
    "QAClassification",
    "QAExecutionMode",
    "QAFindingStatus",
    "QA_CATEGORIES",
    "QA_SEVERITIES",
    "QA_GATES",
    "QA_STATUSES",
    "QA_CLASSIFICATIONS",
    "QA_EXECUTION_MODES",
    "QA_FINDING_STATUSES",
    "QA_DIMENSIONS",
    "SEVERITY_WEIGHTS",
    "is_blocking_severity",
    "compute_gate",
]
