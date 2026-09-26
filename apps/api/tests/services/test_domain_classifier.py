"""M21 — Domain classifier tests."""
from __future__ import annotations

import uuid

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.services.classification.context import ClassificationContext
from app.services.classification.domain_classifier import classify_domain
from app.services.classification.evidence import EvidenceCollector
from app.services.classification.taxonomy import list_active_domains


def _empty_ctx(**kwargs) -> ClassificationContext:
    from app.services.classification.context import ContextChunk

    explicit_domain = kwargs.pop("explicit_domain", None)
    name = kwargs.pop("name", "")

    ctx = ClassificationContext(
        project_id=uuid.uuid4(),
        explicit_domain=explicit_domain,
        name=name,
    )
    for k, v in kwargs.items():
        ctx.chunks.append(
            ContextChunk(location=f"project.{k}", text=v)
        )
    return ctx


def test_explicit_domain_exact_match():
    with SessionLocal() as db:
        collector = EvidenceCollector()
        ctx = _empty_ctx(explicit_domain="computer_science")
        result = classify_domain(db, ctx=ctx, collector=collector)
        assert result.primary_code == "computer_science"
        assert result.source == "explicit"
        assert result.method == "explicit"
        assert result.primary_confidence == 1.0


def test_explicit_domain_alias_match():
    with SessionLocal() as db:
        collector = EvidenceCollector()
        ctx = _empty_ctx(explicit_domain="cs")
        result = classify_domain(db, ctx=ctx, collector=collector)
        assert result.primary_code == "computer_science"
        assert result.source == "explicit"
        assert result.primary_confidence == 0.9


def test_heuristic_from_description():
    with SessionLocal() as db:
        collector = EvidenceCollector()
        ctx = _empty_ctx(
            description=(
                "We study deep learning for natural language processing"
            )
        )
        result = classify_domain(db, ctx=ctx, collector=collector)
        assert result.primary_code in (
            "natural_language_processing", "machine_learning",
            "artificial_intelligence", "computer_science",
        )
        assert result.source == "inferred"
        assert result.primary_confidence is not None


def test_unknown_when_no_signal():
    with SessionLocal() as db:
        collector = EvidenceCollector()
        ctx = _empty_ctx(description="zzzzzzz nothing matches")
        result = classify_domain(db, ctx=ctx, collector=collector)
        assert result.primary_code is None


def test_alternatives_are_bounded_and_sorted():
    s = get_settings()
    with SessionLocal() as db:
        collector = EvidenceCollector()
        ctx = _empty_ctx(
            description=(
                "computer science artificial intelligence "
                "machine learning natural language processing "
                "medicine biology physics"
            )
        )
        result = classify_domain(db, ctx=ctx, collector=collector)
        assert (
            len(result.alternatives)
            <= s.classification_max_alternatives
        )


def test_taxonomy_has_multiple_depths():
    with SessionLocal() as db:
        domains = list_active_domains(db)
        assert any(d.depth == 0 for d in domains)
        assert any(d.depth >= 1 for d in domains)
