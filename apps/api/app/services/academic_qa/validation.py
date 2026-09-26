"""M31 — Run output validation."""
from __future__ import annotations

from dataclasses import dataclass, field

from app.services.academic_qa.findings import QAFinding


@dataclass
class ValidationResult:
    status: str
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def validate_findings(
    findings: list[QAFinding],
) -> ValidationResult:
    errors: list[str] = []
    warnings: list[str] = []
    for f in findings:
        if not f.rule_id:
            errors.append("finding_missing_rule_id")
        if not f.category:
            errors.append(f"finding_missing_category:{f.rule_id}")
        if not f.title:
            errors.append(f"finding_missing_title:{f.rule_id}")
        if f.classification == "model_assisted" and f.confidence is None:
            warnings.append(f"model_assisted_without_confidence:{f.rule_id}")
    return ValidationResult(
        status="valid" if not errors else "invalid",
        errors=errors,
        warnings=warnings,
    )


__all__ = ["ValidationResult", "validate_findings"]
