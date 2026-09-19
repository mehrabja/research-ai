"""M21 — Research-design classifier tests."""
from __future__ import annotations

import uuid

from app.services.classification.context import (
    ClassificationContext,
    ContextChunk,
)
from app.services.classification.evidence import EvidenceCollector
from app.services.classification.research_design_classifier import (
    classify_research_design,
)


def _ctx_with(*, objective: str = "", description: str = "") -> ClassificationContext:
    ctx = ClassificationContext(
        project_id=uuid.uuid4(), explicit_domain=None, name=""
    )
    if objective:
        ctx.chunks.append(
            ContextChunk(
                location="project.research_objective", text=objective
            )
        )
    if description:
        ctx.chunks.append(
            ContextChunk(location="project.description", text=description)
        )
    return ctx


def test_cohort_detected():
    collector = EvidenceCollector()
    ctx = _ctx_with(
        objective="We conducted a cohort study of 1000 subjects",
    )
    r = classify_research_design(
        ctx, paper_type_code=None, collector=collector
    )
    assert r.primary_code == "cohort"


def test_rct_detected():
    collector = EvidenceCollector()
    ctx = _ctx_with(
        description="randomized controlled trial with 200 patients",
    )
    r = classify_research_design(
        ctx, paper_type_code=None, collector=collector
    )
    assert r.primary_code == "randomized_controlled_trial"


def test_paper_type_prior_present():
    collector = EvidenceCollector()
    ctx = _ctx_with()  # empty context
    r = classify_research_design(
        ctx, paper_type_code="systematic_review", collector=collector
    )
    assert r.primary_code == "systematic_review"


def test_unknown_when_no_signal():
    collector = EvidenceCollector()
    ctx = _ctx_with(description="lorem ipsum")
    r = classify_research_design(
        ctx, paper_type_code=None, collector=collector
    )
    assert r.primary_code == "unknown"
