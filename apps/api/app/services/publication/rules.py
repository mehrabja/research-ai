"""M33 — Deterministic compliance rules.

No LLM. Rules are profile-driven; when a rule's required target
metadata is absent, the rule is skipped (fail-open at rule level,
not at compliance level).
"""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.citation import CitationRun, Claim, ClaimCitation
from app.db.models.manuscript import ManuscriptSection
from app.db.models.publication import PublicationTarget
from app.domain.publication import (
    CitationStyle,
    ComplianceCategory,
    ComplianceSeverity,
)
from app.services.publication.findings import ComplianceFinding


@dataclass
class Snapshot:
    project_id: uuid.UUID
    report_id: uuid.UUID
    manuscript_id: uuid.UUID
    manuscript_version_id: uuid.UUID
    target: PublicationTarget
    sections: list[ManuscriptSection] = field(default_factory=list)
    m30_citation_style: str | None = None
    m30_claim_count: int = 0
    m30_citation_count: int = 0


def build_snapshot(
    db: Session,
    *,
    project_id: uuid.UUID,
    report_id: uuid.UUID,
    manuscript_id: uuid.UUID,
    manuscript_version_id: uuid.UUID,
    target_id: uuid.UUID,
) -> Snapshot:
    sections = list(db.execute(
        select(ManuscriptSection)
        .where(
            ManuscriptSection.manuscript_version_id
            == manuscript_version_id
        )
        .order_by(ManuscriptSection.display_order.asc())
    ).scalars().all())

    target = db.get(PublicationTarget, target_id)
    if target is None:
        raise ValueError("target not found")

    m30_run = db.execute(
        select(CitationRun)
        .where(
            CitationRun.report_id == report_id,
            CitationRun.status == "completed",
        )
        .order_by(
            CitationRun.created_at.desc(),
            CitationRun.id.desc(),
        )
        .limit(1)
    ).scalar_one_or_none()

    m30_style: str | None = None
    claim_count = 0
    citation_count = 0
    if m30_run is not None:
        m30_style = m30_run.citation_style
        claim_count = m30_run.claim_count
        citation_count = m30_run.citation_count

    _ = Claim, ClaimCitation  # reserved for future rules
    return Snapshot(
        project_id=project_id,
        report_id=report_id,
        manuscript_id=manuscript_id,
        manuscript_version_id=manuscript_version_id,
        target=target,
        sections=sections,
        m30_citation_style=m30_style,
        m30_claim_count=claim_count,
        m30_citation_count=citation_count,
    )


# ---------------------------------------------------------------------------
# Rules
# ---------------------------------------------------------------------------


def rule_citation_style_match(snap: Snapshot) -> list[ComplianceFinding]:
    target_style = snap.target.citation_style
    if target_style == CitationStyle.NUMERIC.value:
        expected = "numeric"
    elif target_style == CitationStyle.AUTHOR_YEAR.value:
        expected = "author_year"
    else:
        return []  # footnote etc: no M30 equivalent
    if snap.m30_citation_style and snap.m30_citation_style != expected:
        return [ComplianceFinding(
            rule_id="citation_style.mismatch",
            category=ComplianceCategory.CITATION_STYLE.value,
            severity=ComplianceSeverity.WARNING.value,
            title="Citation style does not match target",
            message=(
                f"Target requires '{expected}' but M30 run used "
                f"'{snap.m30_citation_style}'."
            ),
            evidence={
                "target_style": expected,
                "actual_style": snap.m30_citation_style,
            },
        )]
    return []


def rule_required_sections(snap: Snapshot) -> list[ComplianceFinding]:
    rules = snap.target.section_rules or {}
    required_keys = rules.get("required_keys")
    if not required_keys:
        return []
    present = {s.section_key for s in snap.sections if s.status == "active"}
    missing = [k for k in required_keys if k not in present]
    if not missing:
        return []
    return [ComplianceFinding(
        rule_id="section_structure.required_missing",
        category=ComplianceCategory.SECTION_STRUCTURE.value,
        severity=ComplianceSeverity.BLOCKING.value,
        title="Required section(s) missing",
        message=f"Target requires sections: {', '.join(missing)}",
        evidence={"missing": missing, "present": sorted(present)},
    )]


def rule_section_order(snap: Snapshot) -> list[ComplianceFinding]:
    rules = snap.target.section_rules or {}
    expected_order = rules.get("expected_order")
    if not expected_order:
        return []
    present = {s.section_key for s in snap.sections if s.status == "active"}
    sequence = [k for k in expected_order if k in present]
    actual = [
        s.section_key
        for s in sorted(snap.sections, key=lambda x: x.display_order)
        if s.status == "active"
    ]
    if sequence != actual:
        return [ComplianceFinding(
            rule_id="section_structure.order_mismatch",
            category=ComplianceCategory.SECTION_STRUCTURE.value,
            severity=ComplianceSeverity.WARNING.value,
            title="Section order does not match target",
            message=(
                "Observed section order differs from the target's "
                "expected_order."
            ),
            evidence={
                "expected": sequence,
                "actual": actual,
            },
        )]
    return []


def rule_word_limits(snap: Snapshot) -> list[ComplianceFinding]:
    limits = snap.target.word_limits or {}
    total_max = limits.get("total_max")
    if not total_max:
        return []
    total = sum(int(s.word_budget or 0) for s in snap.sections)
    if total > int(total_max):
        return [ComplianceFinding(
            rule_id="word_count.total_exceeds",
            category=ComplianceCategory.WORD_COUNT.value,
            severity=ComplianceSeverity.WARNING.value,
            title="Manuscript word budget exceeds target",
            message=(
                f"Manuscript budget {total} exceeds target max "
                f"{total_max}."
            ),
            evidence={"total": total, "max": int(total_max)},
        )]
    return []


def rule_abstract_limits(snap: Snapshot) -> list[ComplianceFinding]:
    limits = snap.target.abstract_limits or {}
    max_words = limits.get("max_words")
    if not max_words:
        return []
    # Abstract section by convention uses section_key 'abstract'
    abstract = next(
        (s for s in snap.sections if s.section_key == "abstract"),
        None,
    )
    if abstract is None:
        return [ComplianceFinding(
            rule_id="abstract.missing",
            category=ComplianceCategory.ABSTRACT.value,
            severity=ComplianceSeverity.ERROR.value,
            title="Abstract section missing",
            message="Target expects an abstract but none was found.",
        )]
    if int(abstract.word_budget or 0) > int(max_words):
        return [ComplianceFinding(
            rule_id="abstract.exceeds",
            category=ComplianceCategory.ABSTRACT.value,
            severity=ComplianceSeverity.WARNING.value,
            title="Abstract exceeds target limit",
            message=(
                f"Abstract budget {abstract.word_budget} exceeds "
                f"target max {max_words}."
            ),
            evidence={
                "budget": int(abstract.word_budget or 0),
                "max": int(max_words),
            },
        )]
    return []


def rule_keywords(snap: Snapshot) -> list[ComplianceFinding]:
    rules = snap.target.keyword_rules or {}
    min_count = rules.get("min_count")
    max_count = rules.get("max_count")
    if min_count is None and max_count is None:
        return []
    # Keywords are not modelled in M27 yet; emit an informational
    # finding so the reviewer knows the check is pending content.
    _ = re  # reserved
    return [ComplianceFinding(
        rule_id="keywords.not_evaluated",
        category=ComplianceCategory.KEYWORDS.value,
        severity=ComplianceSeverity.INFO.value,
        title="Keyword policy declared",
        message=(
            "Target declares a keyword policy; keyword content is not "
            "yet present in the manuscript model."
        ),
        meta={
            "min_count": min_count,
            "max_count": max_count,
        },
    )]


def rule_mandatory_declarations(snap: Snapshot) -> list[ComplianceFinding]:
    rules = snap.target.reference_rules or {}
    declarations = rules.get("mandatory_declarations")
    if not declarations:
        return []
    _ = declarations
    return [ComplianceFinding(
        rule_id="declarations.not_evaluated",
        category=ComplianceCategory.MANDATORY_DECLARATIONS.value,
        severity=ComplianceSeverity.INFO.value,
        title="Mandatory declarations declared by target",
        message=(
            "Target declares mandatory declarations; declaration "
            "content is not yet tracked."
        ),
    )]


ALL_RULES = (
    rule_citation_style_match,
    rule_required_sections,
    rule_section_order,
    rule_word_limits,
    rule_abstract_limits,
    rule_keywords,
    rule_mandatory_declarations,
)


def run_all_rules(snap: Snapshot) -> list[ComplianceFinding]:
    out: list[ComplianceFinding] = []
    for rule in ALL_RULES:
        try:
            out.extend(rule(snap))
        except Exception as exc:  # noqa: BLE001
            out.append(ComplianceFinding(
                rule_id=f"internal.rule_failed:{rule.__name__}",
                category=ComplianceCategory.MANUSCRIPT_COMPLETENESS.value,
                severity=ComplianceSeverity.ERROR.value,
                title=f"Compliance rule failed: {rule.__name__}",
                message=str(exc)[:300],
                meta={"rule": rule.__name__},
            ))
    return out


def build_checklist_state(
    target: PublicationTarget,
    findings: list[ComplianceFinding],
) -> dict[str, Any]:
    checklist = target.submission_checklist or []
    state: list[dict[str, Any]] = []
    for item in checklist:
        if not isinstance(item, dict):
            continue
        key = item.get("key") or item.get("id")
        required = bool(item.get("required"))
        state.append({
            "key": key,
            "label": item.get("label") or key,
            "required": required,
            "status": "unknown",
        })
    return {
        "items": state,
        "target_code": target.target_code,
        "profile_version": target.profile_version,
    }


__all__ = [
    "Snapshot",
    "build_snapshot",
    "ALL_RULES",
    "run_all_rules",
    "build_checklist_state",
]
