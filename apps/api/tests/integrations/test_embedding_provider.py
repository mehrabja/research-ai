"""Provider adapter tests. No live network calls."""
from __future__ import annotations

import httpx
import pytest

from app.domain.embeddings import EmbeddingProfile
from app.integrations.embeddings.base import (
    EmbeddingAuthenticationError,
    EmbeddingInvalidRequestError,
    EmbeddingInvalidResponseError,
    EmbeddingProviderUnavailableError,
    EmbeddingRateLimitError,
)
from app.integrations.embeddings.openai import OpenAIEmbeddingProvider


def _profile() -> EmbeddingProfile:
    return EmbeddingProfile(
        provider="openai",
        model="text-embedding-3-small",
        dimensions=3,
        distance_metric="cosine",
        profile_version="m9.1-test",
    )


def _patch_post(monkeypatch, responder):  # type: ignore[no-untyped-def]
    import app.integrations.embeddings.openai as mod
    monkeypatch.setattr(mod.httpx, "post", lambda *a, **k: responder())


def _response(
    *, status_code=200, body=None, headers=None
) -> httpx.Response:
    return httpx.Response(
        status_code=status_code,
        json=body,
        headers=headers or {},
        request=httpx.Request("POST", "http://test/"),
    )


def test_basic_success(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    _patch_post(
        monkeypatch,
        lambda: _response(
            body={
                "data": [
                    {"index": 0, "embedding": [0.1, 0.2, 0.3]},
                    {"index": 1, "embedding": [0.4, 0.5, 0.6]},
                ],
                "usage": {"prompt_tokens": 12},
            },
            headers={"x-request-id": "req-1"},
        ),
    )
    p = OpenAIEmbeddingProvider(profile=_profile(), api_key="k")
    r = p.embed_documents(["a", "b"])
    assert len(r.vectors) == 2
    assert r.usage.input_tokens == 12
    assert r.provider_request_id == "req-1"


def test_out_of_order_index_reordered(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    _patch_post(
        monkeypatch,
        lambda: _response(
            body={
                "data": [
                    {"index": 1, "embedding": [0.4, 0.5, 0.6]},
                    {"index": 0, "embedding": [0.1, 0.2, 0.3]},
                ],
                "usage": {"prompt_tokens": 2},
            },
        ),
    )
    p = OpenAIEmbeddingProvider(profile=_profile(), api_key="k")
    r = p.embed_documents(["a", "b"])
    assert r.vectors[0] == [0.1, 0.2, 0.3]
    assert r.vectors[1] == [0.4, 0.5, 0.6]


def test_429_maps_to_rate_limit(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    _patch_post(monkeypatch, lambda: _response(status_code=429))
    p = OpenAIEmbeddingProvider(
        profile=_profile(), api_key="k", max_retries=0
    )
    with pytest.raises(EmbeddingRateLimitError):
        p.embed_documents(["x"])


def test_401_maps_to_auth(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    _patch_post(monkeypatch, lambda: _response(status_code=401))
    p = OpenAIEmbeddingProvider(
        profile=_profile(), api_key="k", max_retries=0
    )
    with pytest.raises(EmbeddingAuthenticationError):
        p.embed_documents(["x"])


def test_400_maps_to_invalid_request(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    _patch_post(monkeypatch, lambda: _response(status_code=400))
    p = OpenAIEmbeddingProvider(
        profile=_profile(), api_key="k", max_retries=0
    )
    with pytest.raises(EmbeddingInvalidRequestError):
        p.embed_documents(["x"])


def test_zero_vector_rejected(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    _patch_post(
        monkeypatch,
        lambda: _response(
            body={
                "data": [
                    {"index": 0, "embedding": [0.0, 0.0, 0.0]}
                ],
                "usage": {"prompt_tokens": 1},
            }
        ),
    )
    p = OpenAIEmbeddingProvider(profile=_profile(), api_key="k")
    with pytest.raises(EmbeddingInvalidResponseError):
        p.embed_documents(["x"])


def test_wrong_dimension_rejected(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    _patch_post(
        monkeypatch,
        lambda: _response(
            body={
                "data": [{"index": 0, "embedding": [0.1, 0.2]}],
                "usage": {"prompt_tokens": 1},
            }
        ),
    )
    p = OpenAIEmbeddingProvider(profile=_profile(), api_key="k")
    with pytest.raises(EmbeddingInvalidResponseError):
        p.embed_documents(["x"])


def test_count_mismatch_rejected(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    _patch_post(
        monkeypatch,
        lambda: _response(
            body={
                "data": [
                    {"index": 0, "embedding": [0.1, 0.2, 0.3]}
                ],
                "usage": {"prompt_tokens": 1},
            }
        ),
    )
    p = OpenAIEmbeddingProvider(profile=_profile(), api_key="k")
    with pytest.raises(EmbeddingInvalidResponseError):
        p.embed_documents(["a", "b"])


def test_transport_error(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    def _boom(*a, **k):  # type: ignore[no-untyped-def]
        raise httpx.ConnectError("no route")
    import app.integrations.embeddings.openai as mod
    monkeypatch.setattr(mod.httpx, "post", _boom)
    p = OpenAIEmbeddingProvider(
        profile=_profile(), api_key="k", max_retries=0
    )
    with pytest.raises(EmbeddingProviderUnavailableError):
        p.embed_documents(["x"])


def test_retry_bounded_delay(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    delays: list[float] = []
    p = OpenAIEmbeddingProvider(
        profile=_profile(),
        api_key="k",
        max_retries=3,
        retry_base_seconds=1.0,
        retry_max_seconds=5.0,
        _sleep=lambda d: delays.append(d),
        _random=lambda: 1.0,
    )
    attempts = {"n": 0}

    def _boom(*a, **k):  # type: ignore[no-untyped-def]
        attempts["n"] += 1
        raise httpx.ConnectError("no route")
    import app.integrations.embeddings.openai as mod
    monkeypatch.setattr(mod.httpx, "post", _boom)

    with pytest.raises(EmbeddingProviderUnavailableError):
        p.embed_documents(["x"])
    assert attempts["n"] == 4
    assert all(d <= 5.0 for d in delays)


def test_tiktoken_estimate_matches_encoder() -> None:
    p = OpenAIEmbeddingProvider(profile=_profile(), api_key="k")
    if p._encoding is None:
        pytest.skip("tiktoken not available")
    text = "hello world"
    expected = len(p._encoding.encode(text))
    assert p.estimate_input_tokens(text) == expected


def test_unknown_model_token_count_none() -> None:
    p = OpenAIEmbeddingProvider(
        profile=EmbeddingProfile(
            provider="openai",
            model="model-does-not-exist-xyz",
            dimensions=3,
            distance_metric="cosine",
            profile_version="t",
        ),
        api_key="k",
    )
    assert p.estimate_input_tokens("x") is None


def test_openrouter_prefixed_embedding_model_uses_tiktoken_family(monkeypatch) -> None:
    import app.integrations.embeddings.openai as module

    class _FakeEncoding:
        def encode(self, text: str) -> list[int]:
            return list(range(len(text)))

    monkeypatch.setattr(module, "_load_tiktoken_encoding", lambda model: _FakeEncoding())
    monkeypatch.setattr(module, "get_settings", lambda: type(
        "S", (), {
            "embedding_openai_base_url": "https://api.openai.com/v1",
            "embedding_openai_api_key": "key",
            "embedding_timeout_seconds": 30.0,
            "embedding_max_retries": 0,
            "embedding_retry_base_seconds": 1.0,
            "embedding_retry_max_seconds": 30.0,
            "embedding_retry_jitter_fraction": 0.0,
            "openrouter_http_referer": "",
            "openrouter_app_title": "Research AI",
        }
    )())
    profile = module.EmbeddingProfile(
        provider="openrouter",
        model="openai/text-embedding-3-small",
        dimensions=1536,
        distance_metric="cosine",
        profile_version="test",
    )
    provider = module.OpenAIEmbeddingProvider(profile=profile, api_key="key", base_url="https://openrouter.ai/api/v1", provider_name="openrouter")
    assert provider.estimate_input_tokens("abcd") == 4
