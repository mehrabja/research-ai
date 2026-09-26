"""M28 — Context hash tests (no DB)."""
from __future__ import annotations

import uuid

from app.domain.embeddings import EmbeddingProfile
from app.services.section_research import context as ctx_svc


def _profile() -> EmbeddingProfile:
    return EmbeddingProfile(
        provider="openai",
        model="text-embedding-3-small",
        dimensions=1536,
        distance_metric="cosine",
        profile_version="m9.1",
    )


def _profile_alt() -> EmbeddingProfile:
    return EmbeddingProfile(
        provider="openai",
        model="text-embedding-3-large",
        dimensions=1536,
        distance_metric="cosine",
        profile_version="m9.2",
    )


def _kwargs(**overrides) -> dict:
    base = {
        "project_id": uuid.uuid4(),
        "report_id": uuid.uuid4(),
        "manuscript_version_id": uuid.uuid4(),
        "manuscript_section_id": uuid.uuid4(),
        "contract_hash": "abc123",
        "profile": _profile(),
        "mode": "lexical",
        "algorithm": "ann",
        "effective_filters": {
            "min_year": None,
            "max_year": None,
            "required_full_text": False,
            "allowed_source_ids": [],
            "preferred_paper_types": [],
            "preferred_research_designs": [],
            "min_relevance_score": None,
        },
        "effective_max_results": 20,
        "candidate_limit": 80,
    }
    base.update(overrides)
    return base


def test_context_hash_is_deterministic():
    kw = _kwargs()
    h1 = ctx_svc.compute_section_research_context_hash(**kw)
    h2 = ctx_svc.compute_section_research_context_hash(**kw)
    assert h1 == h2
    assert isinstance(h1, str)
    assert len(h1) == 32


def test_context_hash_changes_on_different_section():
    kw = _kwargs()
    h1 = ctx_svc.compute_section_research_context_hash(**kw)
    kw["manuscript_section_id"] = uuid.uuid4()
    h2 = ctx_svc.compute_section_research_context_hash(**kw)
    assert h1 != h2


def test_context_hash_changes_on_different_contract_hash():
    kw = _kwargs()
    h1 = ctx_svc.compute_section_research_context_hash(**kw)
    kw["contract_hash"] = "different_hash"
    h2 = ctx_svc.compute_section_research_context_hash(**kw)
    assert h1 != h2


def test_context_hash_changes_on_different_profile():
    kw = _kwargs()
    h1 = ctx_svc.compute_section_research_context_hash(**kw)
    kw["profile"] = _profile_alt()
    h2 = ctx_svc.compute_section_research_context_hash(**kw)
    assert h1 != h2


def test_context_hash_changes_on_different_filters():
    kw = _kwargs()
    h1 = ctx_svc.compute_section_research_context_hash(**kw)
    kw["effective_filters"] = {
        **kw["effective_filters"],
        "max_year": 2026,
    }
    h2 = ctx_svc.compute_section_research_context_hash(**kw)
    assert h1 != h2


def test_context_hash_changes_on_different_max_results():
    kw = _kwargs()
    h1 = ctx_svc.compute_section_research_context_hash(**kw)
    kw["effective_max_results"] = 50
    h2 = ctx_svc.compute_section_research_context_hash(**kw)
    assert h1 != h2


def test_context_hash_ignores_filter_dict_key_order():
    kw1 = _kwargs()
    kw2 = _kwargs()
    kw2["effective_filters"] = {
        "min_relevance_score": None,
        "preferred_research_designs": [],
        "preferred_paper_types": [],
        "allowed_source_ids": [],
        "required_full_text": False,
        "max_year": None,
        "min_year": None,
    }
    for k in (
        "project_id", "report_id", "manuscript_version_id",
        "manuscript_section_id", "contract_hash",
    ):
        kw2[k] = kw1[k]
    h1 = ctx_svc.compute_section_research_context_hash(**kw1)
    h2 = ctx_svc.compute_section_research_context_hash(**kw2)
    assert h1 == h2
