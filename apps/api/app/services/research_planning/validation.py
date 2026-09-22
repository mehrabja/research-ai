"""M24 — Structure + completeness validation."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ValidationResult:
    score: float
    errors: list[str]
    warnings: list[str]

    def valid(self) -> bool:
        return not self.errors


def validate_plan_structure(
    *,
    sections: list,
    requirements: list,
    budget: dict,
    dependency_edges: list[tuple[str, str]],
    plan_section_key_of,
    category_resolved: bool,
) -> ValidationResult:
    errors: list[str] = []
    warnings: list[str] = []

    if not category_resolved:
        warnings.append("classification missing or fallback used")

    if not sections:
        errors.append("no sections")

    keys = [s.section_key for s in sections]
    if len(keys) != len(set(keys)):
        errors.append("duplicate section keys")

    orders = [s.display_order for s in sections]
    if sorted(orders) != list(range(len(orders))):
        errors.append(
            "display_order is not a continuous 0..N-1 sequence"
        )

    for s in sections:
        if not s.title:
            errors.append(f"section {s.section_key}: missing title")
        if not s.purpose:
            warnings.append(
                f"section {s.section_key}: missing purpose"
            )
        if s.required and s.word_budget <= 0:
            errors.append(
                f"required section {s.section_key}: "
                "word_budget must be > 0"
            )

    allocs = budget.get("section_allocations") or {}
    for s in sections:
        if s.section_key not in allocs:
            errors.append(
                f"section {s.section_key}: missing budget allocation"
            )

    req_sections = {r.section_key for r in requirements}
    for s in sections:
        if s.required and s.section_key not in req_sections:
            errors.append(
                f"required section {s.section_key}: "
                "no evidence requirements"
            )

    req_keys = [r.requirement_key for r in requirements]
    if len(req_keys) != len(set(req_keys)):
        errors.append("duplicate requirement keys")

    from app.services.research_planning.dependencies import detect_cycle

    cycle = detect_cycle(keys, dependency_edges)
    if cycle is not None:
        errors.append(
            "dependency cycle detected: " + " -> ".join(cycle)
        )

    total_checks = (
        1 + 1 + 1
        + len(sections)
        + len(sections)
        + 1 + 1
    )
    passed = 0
    if sections:
        passed += 1
    if len(keys) == len(set(keys)):
        passed += 1
    if sorted(orders) == list(range(len(orders))):
        passed += 1
    passed += sum(1 for s in sections if s.title)
    passed += sum(1 for s in sections if s.section_key in allocs)
    if len(req_keys) == len(set(req_keys)):
        passed += 1
    if cycle is None:
        passed += 1
    score = passed / total_checks if total_checks else 0.0

    return ValidationResult(score=score, errors=errors, warnings=warnings)
