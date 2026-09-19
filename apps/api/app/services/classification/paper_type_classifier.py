"""M21 — Paper-type classifier (heuristic-first)."""
from __future__ import annotations

from dataclasses import dataclass, field

from app.core.config import get_settings
from app.services.classification.context import ClassificationContext
from app.services.classification.evidence import (
    EvidenceCollector,
    EvidenceItem,
)
from app.services.classification.text_match import contains_alias

_KEYWORD_RULES: tuple[tuple[str, tuple[str, ...], float], ...] = (
    ("systematic_review", (
        "systematic review", "systematic literature review",
        "prisma", "cochrane review",
    ), 0.85),
    ("meta_analysis", (
        "meta-analysis", "meta analysis", "pooled analysis",
        "pooled estimate",
    ), 0.9),
    ("scoping_review", (
        "scoping review", "scoping study",
    ), 0.85),
    ("narrative_review", (
        "narrative review", "literature review",
    ), 0.6),
    ("randomized_controlled_trial", (
        "randomized controlled trial", "randomised controlled trial",
        "randomized trial", "randomised trial", "rct",
    ), 0.9),
    ("cohort_study", (
        "cohort study", "cohort analysis", "longitudinal cohort",
    ), 0.8),
    ("case_control_study", (
        "case-control", "case control study",
    ), 0.8),
    ("cross_sectional_study", (
        "cross-sectional", "cross sectional study",
    ), 0.8),
    ("case_report", ("case report", "case study"), 0.7),
    ("case_series", ("case series",), 0.8),
    ("experimental_study", (
        "experimental study", "in vitro", "in vivo",
    ), 0.6),
    ("observational_study", (
        "observational study", "observational cohort",
    ), 0.7),
    ("quasi_experimental_study", (
        "quasi-experimental", "quasi experimental",
    ), 0.8),
    ("methodology_paper", (
        "methodology paper", "methods paper",
    ), 0.7),
    ("technical_paper", (
        "technical paper", "technical report",
    ), 0.6),
    ("theoretical_paper", (
        "theoretical paper", "theoretical analysis",
        "theoretical framework",
    ), 0.6),
    ("dataset_paper", (
        "dataset paper", "data descriptor", "data paper",
    ), 0.85),
    ("software_tool_paper", (
        "software tool", "tool paper", "software paper",
    ), 0.8),
    ("benchmark_paper", (
        "benchmark paper", "benchmark study",
    ), 0.8),
    ("survey_paper", (
        "survey paper", "survey of", "systematic survey",
    ), 0.6),
    ("position_paper", ("position paper",), 0.75),
    ("editorial", ("editorial",), 0.7),
    ("letter", ("letter to the editor",), 0.7),
    ("protocol", ("study protocol", "trial protocol"), 0.85),
    ("conference_paper", (
        "conference paper", "in proceedings of",
    ), 0.7),
    ("thesis", (
        "phd thesis", "doctoral thesis", "master thesis", "dissertation",
    ), 0.8),
    ("original_research", (
        "original research", "original article",
    ), 0.6),
)


_LOCATION_WEIGHTS: dict[str, float] = {
    "project.description": 0.35,
    "project.research_objective": 0.4,
    "project.research_questions": 0.35,
    "project.hypotheses": 0.35,
    "project.scope": 0.3,
    "report:": 0.45,
    "report_version:": 0.3,
    "file:": 0.2,
}


def _weight_for(location: str) -> float:
    for prefix in (
        "project.description", "project.research_objective",
        "project.research_questions", "project.hypotheses",
        "project.scope", "report_version:", "report:", "file:",
    ):
        if location.startswith(prefix):
            return _LOCATION_WEIGHTS[prefix]
    return 0.1


@dataclass
class PaperCandidate:
    code: str
    confidence: float = 0.0
    evidence: list[EvidenceItem] = field(default_factory=list)


@dataclass
class PaperTypeResult:
    primary_code: str | None
    primary_confidence: float | None
    source: str
    method: str
    reason: str | None
    secondary: list[str]
    alternatives: list[dict]
    evidence: list[EvidenceItem]


def _noisy_or(weights: list[float]) -> float:
    p = 1.0
    for w in weights:
        p *= (1.0 - w)
    return 1.0 - p


def classify_paper_type(
    ctx: ClassificationContext,
    collector: EvidenceCollector,
) -> PaperTypeResult:
    settings = get_settings()
    cand: dict[str, PaperCandidate] = {}

    for chunk in ctx.chunks:
        if not chunk.text:
            continue
        loc_w = _weight_for(chunk.location)
        for code, aliases, rule_w in _KEYWORD_RULES:
            for alias in aliases:
                if contains_alias(chunk.text, alias):
                    w = min(rule_w * loc_w, 0.95)
                    ev = EvidenceItem(
                        target="paper_type",
                        signal_type="keyword",
                        source_location=chunk.location,
                        matched_text=alias,
                        weight=w,
                        target_code=code,
                    )
                    collector.add(ev)
                    cand.setdefault(
                        code, PaperCandidate(code=code)
                    ).evidence.append(ev)

    ranked = sorted(
        cand.values(),
        key=lambda c: _noisy_or([e.weight for e in c.evidence]),
        reverse=True,
    )

    if not ranked:
        return PaperTypeResult(
            primary_code="unknown",
            primary_confidence=None,
            source="inferred",
            method="heuristic",
            reason="no keyword matched",
            secondary=[],
            alternatives=[],
            evidence=collector.items_for("paper_type"),
        )

    for c in ranked:
        c.confidence = round(
            _noisy_or([e.weight for e in c.evidence]), 4
        )

    top = ranked[0]
    alts = ranked[1 : settings.classification_max_alternatives + 1]
    secondary = [
        c.code for c in alts
        if c.confidence >= settings.classification_confidence_threshold
    ][: settings.classification_max_secondary_paper_types]

    return PaperTypeResult(
        primary_code=top.code,
        primary_confidence=top.confidence,
        source="inferred",
        method="heuristic",
        reason=f"matched {len(top.evidence)} keyword(s)",
        secondary=secondary,
        alternatives=[
            {"code": c.code, "confidence": c.confidence} for c in alts
        ],
        evidence=collector.items_for("paper_type"),
    )
