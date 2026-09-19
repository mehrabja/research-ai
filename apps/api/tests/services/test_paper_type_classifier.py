"""M21 — Paper-type classifier tests."""
from __future__ import annotations

import uuid

from app.services.classification.context import (
    ClassificationContext,
    ContextChunk,
)
from app.services.classification.evidence import EvidenceCollector
from app.services.classification.paper_type_classifier import (
    classify_paper_type,
)


def _ctx_with(*, topic: str = "", description: str = "") -> ClassificationContext:
    ctx = ClassificationContext(
        project_id=uuid.uuid4(), explicit_domain=None, name=""
    )
    if topic:
        ctx.chunks.append(
            ContextChunk(location="report:x.topic", text=topic)
        )
    if description:
        ctx.chunks.append(
            ContextChunk(location="project.description", text=description)
        )
    return ctx


def test_systematic_review_detected():
    collector = EvidenceCollector()
    ctx = _ctx_with(
        topic="A systematic review of X with PRISMA",
        description="This systematic review evaluates...",
    )
    r = classify_paper_type(ctx, collector)
    assert r.primary_code == "systematic_review"


def test_meta_analysis_detected():
    collector = EvidenceCollector()
    ctx = _ctx_with(
        topic="Meta-analysis of randomized trials",
        description="We conducted a meta-analysis...",
    )
    r = classify_paper_type(ctx, collector)
    assert r.primary_code == "meta_analysis"


def test_rct_detected():
    collector = EvidenceCollector()
    ctx = _ctx_with(
        topic="A randomized controlled trial",
        description="RCT design",
    )
    r = classify_paper_type(ctx, collector)
    assert r.primary_code == "randomized_controlled_trial"


def test_unknown_when_no_match():
    collector = EvidenceCollector()
    ctx = _ctx_with(description="nothing meaningful here 1234")
    r = classify_paper_type(ctx, collector)
    assert r.primary_code == "unknown"


def test_secondary_paper_types_when_multiple_match():
    collector = EvidenceCollector()
    ctx = _ctx_with(
        topic="Systematic review and meta-analysis",
        description="systematic review with meta-analysis",
    )
    r = classify_paper_type(ctx, collector)
    assert r.primary_code in ("systematic_review", "meta_analysis")
    assert r.secondary
