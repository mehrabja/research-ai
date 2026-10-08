"""M39 provider routing and fallback tests."""
from __future__ import annotations

from app.services.provider_registry import (
    EmbeddingProviderFallback,
    GenerationProviderFallback,
    ProviderRegistry,
    ProviderDefinition,
)


class _RateLimitedGeneration:
    provider_name = "openrouter"
    model_name = "openai/gpt-4o-mini"

    def generate(self, **_kwargs):
        from app.integrations.generation.base import GenerationRateLimitError
        raise GenerationRateLimitError("429")


class _WorkingGeneration:
    provider_name = "openai"
    model_name = "gpt-4o-mini"

    def generate(self, **_kwargs):
        from app.domain.generation import GenerationProviderResult
        return GenerationProviderResult(
            text="ok",
            provider=self.provider_name,
            model=self.model_name,
            input_tokens=1,
            output_tokens=1,
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
    provider_name = "openai"

    def embed_documents(self, texts):
        from app.domain.embeddings import EmbeddingBatchResult, EmbeddingUsage
        return EmbeddingBatchResult(
            vectors=[[0.1, 0.2, 0.3] for _ in texts],
            usage=EmbeddingUsage(input_tokens=len(texts)),
        )

    def embed_query(self, text: str) -> list[float]:
        return [0.1, 0.2, 0.3]


def test_generation_fallback_advances_on_retryable_failure() -> None:
    router = GenerationProviderFallback(
        (_RateLimitedGeneration(), _WorkingGeneration())
    )
    result = router.generate(system_prompt="s", user_prompt="u", temperature=0.1, max_output_tokens=10)
    assert result.provider == "openai"
    assert router.attempted_providers == ["openrouter", "openai"]


def test_embedding_fallback_advances_on_provider_unavailable() -> None:
    router = EmbeddingProviderFallback(
        (_UnavailableEmbedding(), _WorkingEmbedding())
    )
    result = router.embed_documents(["x"])
    assert result.vectors == [[0.1, 0.2, 0.3]]
    assert router.attempted_providers == ["openrouter", "openai"]


def test_registry_candidate_order_preserves_requested_provider() -> None:
    registry = ProviderRegistry()
    registry.register(
        ProviderDefinition("openrouter", "generation", lambda _config: _RateLimitedGeneration())
    )
    registry.register(
        ProviderDefinition("openai", "generation", lambda _config: _WorkingGeneration())
    )
    registry.register(
        ProviderDefinition("unused", "generation", lambda _config: _WorkingGeneration(), enabled=False)
    )
    registry.configured_chain = lambda capability: ("openrouter", "openai")  # type: ignore[method-assign]
    defs = registry.candidates("generation", requested="openai")
    assert [item.name for item in defs] == ["openai", "openrouter"]
