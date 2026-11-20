"""M26 — Stage D: LLM decomposition + rerank tests."""
from __future__ import annotations

import uuid

from app.domain.generation import GenerationProviderResult
from app.services.rag import llm_decomposition as dec_svc
from app.services.rag import llm_rerank as rerank_svc


class _FakeProvider:
    def __init__(self, *, text: str | None = None, raise_exc=None):
        self._text = text
        self._raise = raise_exc

    def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_output_tokens: int,
    ) -> GenerationProviderResult:
        if self._raise is not None:
            raise self._raise
        return GenerationProviderResult(
            text=self._text or "",
            provider="fake",
            model="fake-1",
            input_tokens=10,
            output_tokens=20,
            total_tokens=30,
            request_id=None,
        )


def test_decomposition_parses_lines():
    p = _FakeProvider(text="alpha\nbeta\ngamma")
    subs, warns = dec_svc.decompose_query(
        normalized_query="original", provider=p,
    )
    assert subs == ["alpha", "beta", "gamma"]
    assert warns == []


def test_decomposition_strips_numbering():
    p = _FakeProvider(text="1. alpha\n2) beta\n- gamma")
    subs, _ = dec_svc.decompose_query(
        normalized_query="original", provider=p,
    )
    assert subs == ["alpha", "beta", "gamma"]


def test_decomposition_dedupes():
    p = _FakeProvider(text="alpha\nALPHA\nbeta")
    subs, _ = dec_svc.decompose_query(
        normalized_query="original", provider=p,
    )
    assert subs == ["alpha", "beta"]


def test_decomposition_bounds_max():
    lines = "\n".join(f"q{i}" for i in range(20))
    p = _FakeProvider(text=lines)
    subs, _ = dec_svc.decompose_query(
        normalized_query="original", provider=p,
    )
    assert len(subs) <= dec_svc.MAX_SUBQUERIES


def test_decomposition_empty_output_falls_back():
    p = _FakeProvider(text="")
    subs, _ = dec_svc.decompose_query(
        normalized_query="original", provider=p,
    )
    assert subs == ["original"]


def test_decomposition_llm_boundary_error_falls_back():
    from app.integrations.generation.base import (
        GenerationProviderUnavailableError,
    )
    p = _FakeProvider(
        raise_exc=GenerationProviderUnavailableError("boom")
    )
    subs, warns = dec_svc.decompose_query(
        normalized_query="original", provider=p,
    )
    assert subs == ["original"]
    assert "llm_decomposition_fallback" in warns


def _cands(n: int):
    return [
        {
            "chunk_id": str(uuid.uuid4()),
            "score": 1.0 - i * 0.05,
            "snippet": f"text {i}",
        }
        for i in range(n)
    ]


def test_rerank_prompt_marks_evidence_as_untrusted_data():
    cands = _cands(1)
    prompt = rerank_svc._build_user_prompt("q", cands)
    assert "BEGIN_UNTRUSTED_DATA" in prompt
    assert "END_UNTRUSTED_DATA" in prompt


def test_rerank_valid_order_accepted():
    cands = _cands(3)
    order = [cands[2]["chunk_id"], cands[0]["chunk_id"],
             cands[1]["chunk_id"]]
    p = _FakeProvider(text=str(order).replace("'", '"'))
    out, warns = rerank_svc.rerank_candidates(
        normalized_query="q", candidates=cands, provider=p,
    )
    assert [c["chunk_id"] for c in out] == order
    assert warns == []


def test_rerank_unknown_id_falls_back():
    cands = _cands(3)
    p = _FakeProvider(text='["not-a-real-id"]')
    out, warns = rerank_svc.rerank_candidates(
        normalized_query="q", candidates=cands, provider=p,
    )
    assert [c["chunk_id"] for c in out] == [
        c["chunk_id"] for c in cands
    ]
    assert "llm_rerank_fallback" in warns


def test_rerank_duplicate_ids_fall_back():
    cands = _cands(3)
    dups = [cands[0]["chunk_id"], cands[0]["chunk_id"]]
    p = _FakeProvider(text=str(dups).replace("'", '"'))
    out, warns = rerank_svc.rerank_candidates(
        normalized_query="q", candidates=cands, provider=p,
    )
    assert [c["chunk_id"] for c in out] == [
        c["chunk_id"] for c in cands
    ]
    assert "llm_rerank_fallback" in warns


def test_rerank_malformed_json_falls_back():
    cands = _cands(3)
    p = _FakeProvider(text="not json at all")
    out, warns = rerank_svc.rerank_candidates(
        normalized_query="q", candidates=cands, provider=p,
    )
    assert [c["chunk_id"] for c in out] == [
        c["chunk_id"] for c in cands
    ]
    assert "llm_rerank_fallback" in warns


def test_rerank_llm_boundary_error_falls_back():
    from app.integrations.generation.base import (
        GenerationProviderUnavailableError,
    )
    cands = _cands(3)
    p = _FakeProvider(
        raise_exc=GenerationProviderUnavailableError("boom")
    )
    out, warns = rerank_svc.rerank_candidates(
        normalized_query="q", candidates=cands, provider=p,
    )
    assert [c["chunk_id"] for c in out] == [
        c["chunk_id"] for c in cands
    ]
    assert "llm_rerank_fallback" in warns


def test_rerank_empty_candidates_returns_empty():
    p = _FakeProvider(text="[]")
    out, warns = rerank_svc.rerank_candidates(
        normalized_query="q", candidates=[], provider=p,
    )
    assert out == []
    assert warns == []


def test_rerank_version_stable():
    assert rerank_svc.LLM_RERANK_VERSION == "m26-rerank-v1"


def test_decomp_version_stable():
    assert dec_svc.LLM_DECOMPOSITION_VERSION == "m26-decomp-v1"
