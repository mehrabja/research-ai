"""M39 provider routing and fallback tests."""
from __future__ import annotations

from app.services.provider_registry import (
    EmbeddingProviderFallback,
    ProviderDefinition,
    ProviderRegistry,
)


class _UnavailableEmbedding:
    provider_name = "openrouter"
    model_name = "openai/text-embedding-3-small"
    dimensions = 3
    max_batch_size = 10
    max_input_tokens_per_item = None
    max_input_tokens_per_request = None

    def estimate_input_tokens(self, text: str) -> int | None:
        return None

    def embed_documents(self, texts):
        from app.integrations.embeddings.base import EmbeddingProviderUnavailableError
        raise EmbeddingProviderUnavailableError("503")

    def embed_query(self, text: str) -> list[float]:
        from app.integrations.embeddings.base import EmbeddingProviderUnavailableError
        raise EmbeddingProviderUnavailableError("503")


class _WorkingEmbedding(_UnavailableEmbedding):
    provider_name = "secondary"

    def embed_documents(self, texts):
        from app.domain.embeddings import EmbeddingBatchResult, EmbeddingUsage
        return EmbeddingBatchResult(
            vectors=[[0.1, 0.2, 0.3] for _ in texts],
            usage=EmbeddingUsage(input_tokens=len(texts)),
        )

    def embed_query(self, text: str) -> list[float]:
        return [0.1, 0.2, 0.3]


class _FakeGeneration:
    provider_name = "secondary"
    model_name = "secondary-model"

    def generate(self, **_kwargs):
        return object()


def test_registry_openrouter_provider_is_preferred_by_default(monkeypatch) -> None:
    monkeypatch.setenv("PROVIDER_GENERATION_CHAIN", "openrouter")
    registry = ProviderRegistry()
    from app.core.config import get_settings

    get_settings.cache_clear()
    assert registry.configured_chain("generation") == ("openrouter",)


def test_embedding_fallback_advances_on_provider_unavailable() -> None:
    router = EmbeddingProviderFallback(
        (_UnavailableEmbedding(), _WorkingEmbedding())
    )
    result = router.embed_documents(["x"])
    assert result.vectors == [[0.1, 0.2, 0.3]]
    assert router.attempted_providers == ["openrouter", "secondary"]


def test_registry_candidate_order_preserves_requested_provider() -> None:
    registry = ProviderRegistry()
    def router_provider(_config):
        return object()

    def direct_provider(_config):
        return object()

    def disabled_provider(_config):
        return _FakeGeneration()

    registry.register(
        ProviderDefinition("openrouter", "generation", router_provider)
    )
    registry.register(
        ProviderDefinition("openai", "generation", direct_provider)
    )
    registry.register(
        ProviderDefinition("unused", "generation", disabled_provider, enabled=False)
    )

    def configured_chain(_capability):
        return ("openrouter", "openai")

    registry.configured_chain = configured_chain  # type: ignore[method-assign]
    defs = registry.candidates("generation", requested="openai")
    assert [item.name for item in defs] == ["openai", "openrouter"]


class _TimeoutEmbedding(_UnavailableEmbedding):
    def embed_documents(self, texts):
        from app.integrations.embeddings.base import EmbeddingProviderUnavailableError
        raise EmbeddingProviderUnavailableError("transport timeout")


def test_embedding_fallback_advances_on_provider_unavailable() -> None:
    router = EmbeddingProviderFallback(
        (_TimeoutEmbedding(), _WorkingEmbedding())
    )
    result = router.embed_documents(["x"])
    assert result.vectors == [[0.1, 0.2, 0.3]]
    assert router.attempted_providers == ["openrouter", "secondary"]


def test_embedding_query_fallback_advances_on_provider_unavailable() -> None:
    router = EmbeddingProviderFallback(
        (_TimeoutEmbedding(), _WorkingEmbedding())
    )
    result = router.embed_query("x")
    assert result == [0.1, 0.2, 0.3]
    assert router.attempted_providers == ["openrouter", "openai"]
