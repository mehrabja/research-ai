"""M24 — Deterministic plan templates."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.domain.research_plan import (
    RESEARCH_PLAN_TEMPLATE_VERSION,
)
from app.domain.research_plan import (
    EvidenceRequirementType as ERT,
)
from app.domain.research_plan import (
    SectionType as ST,
)


@dataclass(frozen=True)
class PlanSectionTemplate:
    key: str
    title: str
    purpose: str
    section_type: str
    required: bool
    default_word_weight: float
    evidence_requirements: tuple[dict[str, Any], ...] = field(
        default_factory=tuple
    )


@dataclass(frozen=True)
class ResearchPlanTemplate:
    paper_type_code: str
    template_version: str
    sections: tuple[PlanSectionTemplate, ...]


def _er(
    key: str,
    kind: ERT,
    desc: str,
    *,
    required: bool = True,
    priority: int = 5,
    min_sources: int | None = None,
    max_sources: int | None = None,
    preferred_paper_types: list[str] | None = None,
    preferred_research_designs: list[str] | None = None,
    max_age_years: int | None = None,
    full_text_required: bool = False,
    min_relevance_score: float | None = None,
    coverage_weight: float = 1.0,
) -> dict[str, Any]:
    return {
        "key": key,
        "type": kind.value,
        "description": desc,
        "required": required,
        "priority": priority,
        "min_sources": min_sources,
        "max_sources": max_sources,
        "preferred_paper_types": preferred_paper_types,
        "preferred_research_designs": preferred_research_designs,
        "max_age_years": max_age_years,
        "full_text_required": full_text_required,
        "min_relevance_score": min_relevance_score,
        "coverage_weight": coverage_weight,
    }


def _intro() -> PlanSectionTemplate:
    return PlanSectionTemplate(
        key="introduction",
        title="Introduction",
        purpose="Frame the research problem, objective, and questions.",
        section_type=ST.INTRODUCTION.value,
        required=True,
        default_word_weight=0.10,
        evidence_requirements=(
            _er("intro.background", ERT.BACKGROUND,
                "Background literature establishing the problem space.",
                priority=7, min_sources=3, coverage_weight=1.0),
            _er("intro.theory", ERT.THEORY,
                "Theoretical or conceptual framing.",
                priority=5, min_sources=1, coverage_weight=0.6),
            _er("intro.recent", ERT.RECENT_EVIDENCE,
                "Recent evidence motivating the study.",
                priority=6, max_age_years=5, coverage_weight=0.8),
        ),
    )


def _related_work() -> PlanSectionTemplate:
    return PlanSectionTemplate(
        key="related_work",
        title="Related Work",
        purpose="Synthesize the literature relevant to this study.",
        section_type=ST.RELATED_WORK.value,
        required=True,
        default_word_weight=0.20,
        evidence_requirements=(
            _er("rw.primary", ERT.PRIMARY_STUDY,
                "Primary studies directly relevant.",
                priority=8, min_sources=5, coverage_weight=1.0),
            _er("rw.reviews", ERT.SYSTEMATIC_REVIEW,
                "Reviews or syntheses covering the area.",
                priority=6, min_sources=1, coverage_weight=0.7),
            _er("rw.comparative", ERT.COMPARATIVE,
                "Comparative evidence across approaches.",
                priority=6, min_sources=2, coverage_weight=0.8),
        ),
    )


def _methods(design_code: str | None) -> PlanSectionTemplate:
    preferred_designs = [design_code] if design_code else None
    return PlanSectionTemplate(
        key="methods",
        title="Methods",
        purpose="Describe design, data, and analysis.",
        section_type=ST.METHODS.value,
        required=True,
        default_word_weight=0.20,
        evidence_requirements=(
            _er("methods.methodology", ERT.METHODOLOGY,
                "Methodological references for the chosen design.",
                priority=8, min_sources=2,
                preferred_research_designs=preferred_designs,
                coverage_weight=1.0),
            _er("methods.primary", ERT.PRIMARY_STUDY,
                "Prior primary studies using comparable methods.",
                priority=6, min_sources=3,
                preferred_research_designs=preferred_designs,
                coverage_weight=0.8),
            _er("methods.protocol", ERT.PROTOCOL,
                "Protocols / guidelines for reporting.",
                priority=4, min_sources=1,
                required=False, coverage_weight=0.4),
        ),
    )


def _results() -> PlanSectionTemplate:
    return PlanSectionTemplate(
        key="results",
        title="Results",
        purpose="Present findings.",
        section_type=ST.RESULTS.value,
        required=True,
        default_word_weight=0.15,
        evidence_requirements=(
            _er("results.primary", ERT.PRIMARY_STUDY,
                "Primary studies providing comparative findings.",
                priority=7, min_sources=3, coverage_weight=1.0),
            _er("results.dataset", ERT.DATASET,
                "Datasets or benchmarks used as reference.",
                priority=4, required=False,
                min_sources=0, coverage_weight=0.4),
        ),
    )


def _discussion() -> PlanSectionTemplate:
    return PlanSectionTemplate(
        key="discussion",
        title="Discussion",
        purpose="Interpret findings and place in context.",
        section_type=ST.DISCUSSION.value,
        required=True,
        default_word_weight=0.20,
        evidence_requirements=(
            _er("disc.comparative", ERT.COMPARATIVE,
                "Studies to compare against.",
                priority=8, min_sources=3, coverage_weight=1.0),
            _er("disc.counter", ERT.COUNTER_EVIDENCE,
                "Counter-evidence and contradictions.",
                priority=6, min_sources=1, coverage_weight=0.9),
            _er("disc.limitation", ERT.LIMITATION,
                "Known limitations from prior work.",
                priority=6, min_sources=2, coverage_weight=0.8),
            _er("disc.recent", ERT.RECENT_EVIDENCE,
                "Recent work since publication of core studies.",
                priority=5, max_age_years=3,
                required=False, coverage_weight=0.5),
        ),
    )


def _conclusion() -> PlanSectionTemplate:
    return PlanSectionTemplate(
        key="conclusion",
        title="Conclusion",
        purpose="Summarize contribution and implications.",
        section_type=ST.CONCLUSION.value,
        required=True,
        default_word_weight=0.15,
        evidence_requirements=(
            _er("concl.synthesis", ERT.SYNTHESIS,
                "Synthesis-level references supporting the conclusion.",
                priority=6, min_sources=2, coverage_weight=0.8),
        ),
    )


def _generic_sections() -> tuple[PlanSectionTemplate, ...]:
    return (
        _intro(),
        PlanSectionTemplate(
            key="background",
            title="Background",
            purpose="Context and prior work.",
            section_type=ST.BACKGROUND.value,
            required=True, default_word_weight=0.25,
            evidence_requirements=(
                _er("bg.primary", ERT.PRIMARY_STUDY,
                    "Primary studies providing context.",
                    priority=6, min_sources=3, coverage_weight=1.0),
            ),
        ),
        _methods(design_code=None),
        _discussion(),
        _conclusion(),
    )


def _empirical_sections(
    design_code: str | None,
) -> tuple[PlanSectionTemplate, ...]:
    return (
        _intro(), _related_work(), _methods(design_code),
        _results(), _discussion(), _conclusion(),
    )


def _systematic_review_sections() -> tuple[PlanSectionTemplate, ...]:
    return (
        PlanSectionTemplate(
            key="introduction", title="Introduction",
            purpose="Rationale for the review.",
            section_type=ST.INTRODUCTION.value,
            required=True, default_word_weight=0.10,
            evidence_requirements=(
                _er("intro.background", ERT.BACKGROUND,
                    "Background literature.", priority=6,
                    min_sources=2, coverage_weight=0.8),
            ),
        ),
        PlanSectionTemplate(
            key="methods", title="Methods",
            purpose="Search, screening, and synthesis protocol.",
            section_type=ST.METHODS.value,
            required=True, default_word_weight=0.25,
            evidence_requirements=(
                _er("methods.protocol", ERT.PROTOCOL,
                    "PRISMA / review protocol references.",
                    priority=9, min_sources=1, coverage_weight=1.0),
                _er("methods.systematic", ERT.SYSTEMATIC_REVIEW,
                    "Prior systematic reviews.",
                    priority=6, min_sources=1, coverage_weight=0.7),
            ),
        ),
        PlanSectionTemplate(
            key="results", title="Results",
            purpose="Synthesis of included studies.",
            section_type=ST.RESULTS.value,
            required=True, default_word_weight=0.30,
            evidence_requirements=(
                _er("results.primary", ERT.PRIMARY_STUDY,
                    "Included primary studies.", priority=9,
                    min_sources=5, coverage_weight=1.0),
                _er("results.meta", ERT.META_ANALYSIS,
                    "Meta-analytic syntheses.", priority=4,
                    required=False, min_sources=0, coverage_weight=0.4),
            ),
        ),
        PlanSectionTemplate(
            key="discussion", title="Discussion",
            purpose="Interpretation and limitations.",
            section_type=ST.DISCUSSION.value,
            required=True, default_word_weight=0.20,
            evidence_requirements=(
                _er("disc.limitation", ERT.LIMITATION,
                    "Limitations of the evidence base.",
                    priority=7, min_sources=2, coverage_weight=0.9),
                _er("disc.counter", ERT.COUNTER_EVIDENCE,
                    "Conflicting findings.", priority=5,
                    required=False, min_sources=0, coverage_weight=0.5),
            ),
        ),
        _conclusion(),
    )


def _theoretical_sections() -> tuple[PlanSectionTemplate, ...]:
    return (
        PlanSectionTemplate(
            key="introduction", title="Introduction",
            purpose="Theoretical motivation.",
            section_type=ST.INTRODUCTION.value,
            required=True, default_word_weight=0.15,
            evidence_requirements=(
                _er("intro.theory", ERT.THEORY,
                    "Theoretical foundations.",
                    priority=8, min_sources=3, coverage_weight=1.0),
            ),
        ),
        PlanSectionTemplate(
            key="background", title="Background",
            purpose="Conceptual background.",
            section_type=ST.BACKGROUND.value,
            required=True, default_word_weight=0.35,
            evidence_requirements=(
                _er("bg.theory", ERT.THEORY,
                    "Theories and conceptual frameworks.",
                    priority=7, min_sources=3, coverage_weight=1.0),
            ),
        ),
        PlanSectionTemplate(
            key="discussion", title="Discussion",
            purpose="Implications.",
            section_type=ST.DISCUSSION.value,
            required=True, default_word_weight=0.30,
            evidence_requirements=(
                _er("disc.counter", ERT.COUNTER_EVIDENCE,
                    "Counter-arguments.", priority=6,
                    min_sources=1, coverage_weight=0.8),
            ),
        ),
        _conclusion(),
    )


def _protocol_sections() -> tuple[PlanSectionTemplate, ...]:
    return (
        PlanSectionTemplate(
            key="introduction", title="Introduction",
            purpose="Background and rationale.",
            section_type=ST.INTRODUCTION.value,
            required=True, default_word_weight=0.15,
            evidence_requirements=(
                _er("intro.background", ERT.BACKGROUND,
                    "Background literature.", priority=7,
                    min_sources=3, coverage_weight=1.0),
            ),
        ),
        PlanSectionTemplate(
            key="methods", title="Methods",
            purpose="Planned methods.",
            section_type=ST.METHODS.value,
            required=True, default_word_weight=0.55,
            evidence_requirements=(
                _er("methods.methodology", ERT.METHODOLOGY,
                    "Methodological references.", priority=8,
                    min_sources=2, coverage_weight=1.0),
                _er("methods.protocol", ERT.PROTOCOL,
                    "Reporting guidelines.", priority=7,
                    min_sources=1, coverage_weight=0.9),
            ),
        ),
        PlanSectionTemplate(
            key="discussion", title="Discussion",
            purpose="Expected implications.",
            section_type=ST.DISCUSSION.value,
            required=True, default_word_weight=0.30,
            evidence_requirements=(
                _er("disc.limitation", ERT.LIMITATION,
                    "Anticipated limitations.", priority=5,
                    min_sources=1, required=False,
                    coverage_weight=0.5),
            ),
        ),
    )


def _case_sections() -> tuple[PlanSectionTemplate, ...]:
    return (
        _intro(),
        PlanSectionTemplate(
            key="background", title="Background",
            purpose="Clinical / case context.",
            section_type=ST.BACKGROUND.value,
            required=True, default_word_weight=0.20,
            evidence_requirements=(
                _er("bg.background", ERT.BACKGROUND,
                    "Background literature on the condition.",
                    priority=6, min_sources=2, coverage_weight=1.0),
            ),
        ),
        PlanSectionTemplate(
            key="methods", title="Case Presentation",
            purpose="Case details and methods.",
            section_type=ST.METHODS.value,
            required=True, default_word_weight=0.30,
            evidence_requirements=(
                _er("methods.protocol", ERT.PROTOCOL,
                    "Reporting guidelines (CARE).",
                    priority=5, min_sources=1, coverage_weight=0.6),
            ),
        ),
        _discussion(),
        _conclusion(),
    )


def _dataset_sections() -> tuple[PlanSectionTemplate, ...]:
    return (
        _intro(),
        PlanSectionTemplate(
            key="methods", title="Dataset Construction",
            purpose="Data sources and curation.",
            section_type=ST.METHODS.value,
            required=True, default_word_weight=0.30,
            evidence_requirements=(
                _er("methods.dataset", ERT.DATASET,
                    "Comparable datasets.", priority=7,
                    min_sources=2, coverage_weight=1.0),
                _er("methods.protocol", ERT.PROTOCOL,
                    "Dataset documentation guidelines.",
                    priority=5, required=False,
                    min_sources=0, coverage_weight=0.4),
            ),
        ),
        PlanSectionTemplate(
            key="results", title="Dataset Description",
            purpose="Statistical description and baselines.",
            section_type=ST.RESULTS.value,
            required=True, default_word_weight=0.20,
            evidence_requirements=(
                _er("results.benchmark", ERT.BENCHMARK,
                    "Benchmark comparisons.", priority=5,
                    required=False, min_sources=0,
                    coverage_weight=0.4),
            ),
        ),
        _discussion(),
        _conclusion(),
    )


def _benchmark_sections() -> tuple[PlanSectionTemplate, ...]:
    return (
        _intro(), _related_work(),
        PlanSectionTemplate(
            key="methods", title="Benchmark Design",
            purpose="Task, metrics, and baselines.",
            section_type=ST.METHODS.value,
            required=True, default_word_weight=0.25,
            evidence_requirements=(
                _er("methods.benchmark", ERT.BENCHMARK,
                    "Prior benchmarks.", priority=7,
                    min_sources=2, coverage_weight=1.0),
            ),
        ),
        PlanSectionTemplate(
            key="results", title="Results",
            purpose="Baseline evaluation results.",
            section_type=ST.RESULTS.value,
            required=True, default_word_weight=0.20,
            evidence_requirements=(
                _er("results.benchmark", ERT.BENCHMARK,
                    "Baseline results.", priority=8,
                    min_sources=2, coverage_weight=1.0),
            ),
        ),
        _discussion(), _conclusion(),
    )


def _survey_sections() -> tuple[PlanSectionTemplate, ...]:
    return (
        _intro(),
        PlanSectionTemplate(
            key="methods", title="Survey Methodology",
            purpose="Sampling and instrument.",
            section_type=ST.METHODS.value,
            required=True, default_word_weight=0.25,
            evidence_requirements=(
                _er("methods.methodology", ERT.METHODOLOGY,
                    "Survey methodology references.",
                    priority=7, min_sources=2, coverage_weight=1.0),
            ),
        ),
        PlanSectionTemplate(
            key="results", title="Results",
            purpose="Descriptive and inferential results.",
            section_type=ST.RESULTS.value,
            required=True, default_word_weight=0.25,
            evidence_requirements=(
                _er("results.primary", ERT.PRIMARY_STUDY,
                    "Comparative survey studies.",
                    priority=6, min_sources=2, coverage_weight=0.9),
            ),
        ),
        _discussion(), _conclusion(),
    )


def _methodology_sections() -> tuple[PlanSectionTemplate, ...]:
    return (
        _intro(),
        PlanSectionTemplate(
            key="background", title="Background",
            purpose="Methodological context.",
            section_type=ST.BACKGROUND.value,
            required=True, default_word_weight=0.20,
            evidence_requirements=(
                _er("bg.methodology", ERT.METHODOLOGY,
                    "Prior methodological work.",
                    priority=7, min_sources=3, coverage_weight=1.0),
            ),
        ),
        PlanSectionTemplate(
            key="methods", title="Proposed Method",
            purpose="Method description.",
            section_type=ST.METHODS.value,
            required=True, default_word_weight=0.35,
            evidence_requirements=(
                _er("methods.comparative", ERT.COMPARATIVE,
                    "Baseline methods to compare against.",
                    priority=7, min_sources=2, coverage_weight=1.0),
            ),
        ),
        _results(), _discussion(), _conclusion(),
    )


_TEMPLATES: dict[str, ResearchPlanTemplate] = {}


def _reg(code: str, sections_fn) -> None:
    _TEMPLATES[code] = ResearchPlanTemplate(
        paper_type_code=code,
        template_version=RESEARCH_PLAN_TEMPLATE_VERSION,
        sections=sections_fn(),
    )


def _register_all() -> None:
    _reg("original_research", lambda: _empirical_sections(None))
    _reg("cohort_study", lambda: _empirical_sections("cohort"))
    _reg("case_control_study", lambda: _empirical_sections("case_control"))
    _reg("cross_sectional_study",
         lambda: _empirical_sections("cross_sectional"))
    _reg("randomized_controlled_trial",
         lambda: _empirical_sections("randomized_controlled_trial"))
    _reg("quasi_experimental_study",
         lambda: _empirical_sections("quasi_experimental"))
    _reg("experimental_study", lambda: _empirical_sections("experimental"))
    _reg("observational_study",
         lambda: _empirical_sections("observational"))
    _reg("conference_paper", lambda: _empirical_sections(None))
    _reg("thesis", lambda: _empirical_sections(None))

    _reg("systematic_review", _systematic_review_sections)
    _reg("scoping_review", _systematic_review_sections)
    _reg("narrative_review", _systematic_review_sections)
    _reg("meta_analysis", _systematic_review_sections)

    _reg("case_report", _case_sections)
    _reg("case_series", _case_sections)

    _reg("protocol", _protocol_sections)
    _reg("dataset_paper", _dataset_sections)
    _reg("software_tool_paper", _methodology_sections)
    _reg("benchmark_paper", _benchmark_sections)
    _reg("survey_paper", _survey_sections)
    _reg("methodology_paper", _methodology_sections)
    _reg("technical_paper", _methodology_sections)
    _reg("theoretical_paper", _theoretical_sections)
    _reg("position_paper", _theoretical_sections)

    _reg("editorial", _generic_sections)
    _reg("letter", _generic_sections)
    _reg("unknown", _generic_sections)


_register_all()


def select_template(paper_type_code: str | None) -> ResearchPlanTemplate:
    if paper_type_code and paper_type_code in _TEMPLATES:
        return _TEMPLATES[paper_type_code]
    return _TEMPLATES["unknown"]


def known_paper_types() -> tuple[str, ...]:
    return tuple(sorted(_TEMPLATES.keys()))
