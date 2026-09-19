"""M21 — Research-design classifier (heuristic-first)."""
from __future__ import annotations

from dataclasses import dataclass, field

from app.core.config import get_settings
from app.domain.research_taxonomy import PAPER_TYPE_DEFAULT_DESIGN
from app.services.classification.context import ClassificationContext
from app.services.classification.evidence import (
    EvidenceCollector,
    EvidenceItem,
)
from app.services.classification.text_match import contains_alias

_KEYWORD_RULES: tuple[tuple[str, tuple[str, ...], float], ...] = (
    ("randomized_controlled_trial", (
        "randomized controlled trial", "randomised controlled trial",
        "randomization", "randomly assigned", "randomly allocated",
    ), 0.85),
    ("cohort", (
        "cohort study", "cohort analysis", "follow-up study",
        "longitudinal study",
    ), 0.8),
    ("case_control", ("case-control", "case control"), 0.8),
    ("cross_sectional", (
        "cross-sectional", "cross sectional", "prevalence study",
    ), 0.8),
    ("case_report", ("case report",), 0.75),
    ("case_series", ("case series",), 0.8),
    ("systematic_review", (
        "systematic review", "prisma", "systematic search",
    ), 0.85),
    ("meta_analysis", (
        "meta-analysis", "meta analysis", "pooled estimate",
    ), 0.9),
    ("scoping_review", ("scoping review",), 0.85),
    ("narrative_review", (
        "narrative review", "literature review",
    ), 0.55),
    ("quasi_experimental", (
        "quasi-experimental", "quasi experimental",
    ), 0.85),
    ("experimental", (
        "experimental study", "controlled experiment",
        "in vitro", "in vivo",
    ), 0.55),
    ("observational", (
        "observational study", "observational analysis",
    ), 0.65),
    ("qualitative", (
        "qualitative study", "interviews", "focus group",
        "thematic analysis", "grounded theory",
    ), 0.7),
    ("mixed_methods", ("mixed methods", "mixed-methods"), 0.85),
    ("survey", ("questionnaire", "survey study"), 0.55),
    ("simulation", ("simulation study", "monte carlo"), 0.75),
    ("benchmark", ("benchmark", "benchmarking"), 0.6),
    ("dataset_description", (
        "dataset", "data descriptor", "corpus",
    ), 0.5),
    ("method_development", (
        "method development", "new method", "novel method",
        "proposed method",
    ), 0.55),
    ("theoretical", (
        "theoretical model", "theoretical framework",
        "theoretical analysis", "mathematical proof",
    ), 0.6),
    ("computational", (
        "computational model", "computational study",
    ), 0.6),
)


_LOCATION_WEIGHTS: dict[str, float] = {
    "project.research_objective": 0.5,
    "project.description": 0.4,
    "project.research_questions": 0.35,
    "project.hypotheses": 0.4,
    "report_version:": 0.4,
    "report:": 0.35,
    "file:": 0.25,
}


def _weight_for(location: str) -> float:
    for prefix in (
        "project.research_objective", "project.description",
        "project.research_questions", "project.hypotheses",
        "report_version:", "report:", "file:",
    ):
        if location.startswith(prefix):
            return _LOCATION_WEIGHTS[prefix]
    return 0.1


@dataclass
class DesignCandidate:
    code: str
    confidence: float = 0.0
    evidence: list[EvidenceItem] = field(default_factory=list)


@dataclass
class ResearchDesignResult:
    primary_code: str | None
    primary_confidence: float | None
    source: str
    method: str
    reason: str | None
    alternatives: list[dict]
    evidence: list[EvidenceItem]


def _noisy_or(weights: list[float]) -> float:
    p = 1.0
    for w in weights:
        p *= (1.0 - w)
    return 1.0 - p


def classify_research_design(
    ctx: ClassificationContext,
    *,
    paper_type_code: str | None,
    collector: EvidenceCollector,
) -> ResearchDesignResult:
    settings = get_settings()
    cand: dict[str, DesignCandidate] = {}

    if paper_type_code and paper_type_code in PAPER_TYPE_DEFAULT_DESIGN:
        default_code = PAPER_TYPE_DEFAULT_DESIGN[paper_type_code]
        prior = EvidenceItem(
            target="research_design",
            signal_type="prior",
            source_location="paper_type_prior",
            matched_text=f"paper_type={paper_type_code}",
            weight=0.3,
            target_code=default_code,
        )
        collector.add(prior)
        cand.setdefault(
            default_code, DesignCandidate(code=default_code)
        ).evidence.append(prior)

    for chunk in ctx.chunks:
        if not chunk.text:
            continue
        loc_w = _weight_for(chunk.location)
        for code, aliases, rule_w in _KEYWORD_RULES:
            for alias in aliases:
                if contains_alias(chunk.text, alias):
                    w = min(rule_w * loc_w, 0.9)
                    ev = EvidenceItem(
                        target="research_design",
                        signal_type="keyword",
                        source_location=chunk.location,
                        matched_text=alias,
                        weight=w,
                        target_code=code,
                    )
                    collector.add(ev)
                    cand.setdefault(
                        code, DesignCandidate(code=code)
                    ).evidence.append(ev)

    ranked = sorted(
        cand.values(),
        key=lambda c: _noisy_or([e.weight for e in c.evidence]),
        reverse=True,
    )
    if not ranked:
        return ResearchDesignResult(
            primary_code="unknown",
            primary_confidence=None,
            source="inferred",
            method="heuristic",
            reason="no signal matched",
            alternatives=[],
            evidence=collector.items_for("research_design"),
        )

    for c in ranked:
        c.confidence = round(
            _noisy_or([e.weight for e in c.evidence]), 4
        )

    top = ranked[0]
    alts = ranked[1 : settings.classification_max_alternatives + 1]
    return ResearchDesignResult(
        primary_code=top.code,
        primary_confidence=top.confidence,
        source="inferred",
        method="heuristic",
        reason=f"matched {len(top.evidence)} signal(s)",
        alternatives=[
            {"code": c.code, "confidence": c.confidence} for c in alts
        ],
        evidence=collector.items_for("research_design"),
    )
