"""M21 — Research taxonomy domain (pure)."""
from __future__ import annotations

from enum import StrEnum


class TaxonomyKind(StrEnum):
    DOMAIN = "domain"
    PAPER_TYPE = "paper_type"
    RESEARCH_DESIGN = "research_design"


MAX_DOMAIN_DEPTH = 3


PAPER_TYPE_CODES: tuple[str, ...] = (
    "original_research",
    "systematic_review",
    "scoping_review",
    "narrative_review",
    "meta_analysis",
    "methodology_paper",
    "technical_paper",
    "theoretical_paper",
    "case_report",
    "case_series",
    "cohort_study",
    "case_control_study",
    "cross_sectional_study",
    "randomized_controlled_trial",
    "quasi_experimental_study",
    "experimental_study",
    "observational_study",
    "protocol",
    "dataset_paper",
    "software_tool_paper",
    "benchmark_paper",
    "survey_paper",
    "position_paper",
    "editorial",
    "letter",
    "conference_paper",
    "thesis",
    "unknown",
)


RESEARCH_DESIGN_CODES: tuple[str, ...] = (
    "experimental",
    "observational",
    "randomized_controlled_trial",
    "quasi_experimental",
    "cohort",
    "case_control",
    "cross_sectional",
    "case_report",
    "case_series",
    "systematic_review",
    "scoping_review",
    "narrative_review",
    "meta_analysis",
    "qualitative",
    "mixed_methods",
    "survey",
    "simulation",
    "benchmark",
    "dataset_description",
    "method_development",
    "theoretical",
    "computational",
    "unknown",
)


PAPER_TYPE_DEFAULT_DESIGN: dict[str, str] = {
    "systematic_review": "systematic_review",
    "scoping_review": "scoping_review",
    "narrative_review": "narrative_review",
    "meta_analysis": "meta_analysis",
    "cohort_study": "cohort",
    "case_control_study": "case_control",
    "cross_sectional_study": "cross_sectional",
    "randomized_controlled_trial": "randomized_controlled_trial",
    "quasi_experimental_study": "quasi_experimental",
    "experimental_study": "experimental",
    "observational_study": "observational",
    "case_report": "case_report",
    "case_series": "case_series",
    "dataset_paper": "dataset_description",
    "software_tool_paper": "method_development",
    "benchmark_paper": "benchmark",
    "methodology_paper": "method_development",
    "theoretical_paper": "theoretical",
    "survey_paper": "survey",
    "protocol": "unknown",
}


def is_known_paper_type(code: str) -> bool:
    return code in PAPER_TYPE_CODES


def is_known_research_design(code: str) -> bool:
    return code in RESEARCH_DESIGN_CODES
