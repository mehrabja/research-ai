"""M33 — Journal/Conference targeting domain primitives."""
from __future__ import annotations

from enum import StrEnum

M33_VERSION = "m33.1"
COMPLIANCE_RULES_VERSION = "m33-rules-v1"

# Current profile schema version. Bump when profile JSON shape changes.
PUBLICATION_PROFILE_SCHEMA_VERSION = "m33-profile-v1"


class TargetVenueType(StrEnum):
    JOURNAL = "journal"
    CONFERENCE = "conference"
    WORKSHOP = "workshop"
    PREPRINT = "preprint"
    BOOK_CHAPTER = "book_chapter"
    OTHER = "other"


class CitationStyle(StrEnum):
    NUMERIC = "numeric"
    AUTHOR_YEAR = "author_year"
    FOOTNOTE = "footnote"


class ComplianceSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    BLOCKING = "blocking"


class ComplianceGate(StrEnum):
    PASS = "pass"
    PASS_WITH_WARNINGS = "pass_with_warnings"
    BLOCKED = "blocked"


class ComplianceStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class ComplianceCategory(StrEnum):
    TITLE = "title"
    ABSTRACT = "abstract"
    KEYWORDS = "keywords"
    SECTION_STRUCTURE = "section_structure"
    WORD_COUNT = "word_count"
    CITATION_STYLE = "citation_style"
    BIBLIOGRAPHY_STYLE = "bibliography_style"
    AUTHOR_METADATA = "author_metadata"
    ANONYMIZATION = "anonymization"
    FIGURE_TABLE = "figure_table"
    TERMINOLOGY = "terminology"
    REFERENCES = "references"
    MANDATORY_DECLARATIONS = "mandatory_declarations"
    MANUSCRIPT_COMPLETENESS = "manuscript_completeness"


TARGET_VENUE_TYPES = tuple(t.value for t in TargetVenueType)
CITATION_STYLES = tuple(s.value for s in CitationStyle)
COMPLIANCE_SEVERITIES = tuple(s.value for s in ComplianceSeverity)
COMPLIANCE_GATES = tuple(g.value for g in ComplianceGate)
COMPLIANCE_STATUSES = tuple(s.value for s in ComplianceStatus)
COMPLIANCE_CATEGORIES = tuple(c.value for c in ComplianceCategory)

# Severity weights for gate computation.
COMPLIANCE_SEVERITY_WEIGHTS: dict[str, float] = {
    ComplianceSeverity.INFO.value: 0.0,
    ComplianceSeverity.WARNING.value: 0.1,
    ComplianceSeverity.ERROR.value: 0.4,
    ComplianceSeverity.BLOCKING.value: 1.0,
}


def compute_gate(
    *,
    blocking_count: int,
    error_count: int,
    warning_count: int,
) -> str:
    if blocking_count > 0:
        return ComplianceGate.BLOCKED.value
    if error_count > 0 or warning_count > 0:
        return ComplianceGate.PASS_WITH_WARNINGS.value
    return ComplianceGate.PASS.value


__all__ = [
    "M33_VERSION",
    "COMPLIANCE_RULES_VERSION",
    "PUBLICATION_PROFILE_SCHEMA_VERSION",
    "TargetVenueType",
    "CitationStyle",
    "ComplianceSeverity",
    "ComplianceGate",
    "ComplianceStatus",
    "ComplianceCategory",
    "TARGET_VENUE_TYPES",
    "CITATION_STYLES",
    "COMPLIANCE_SEVERITIES",
    "COMPLIANCE_GATES",
    "COMPLIANCE_STATUSES",
    "COMPLIANCE_CATEGORIES",
    "COMPLIANCE_SEVERITY_WEIGHTS",
    "compute_gate",
]
