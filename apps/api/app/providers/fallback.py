"""Retryable fallback wrapper for provider capability protocols."""
from __future__ import annotations

from typing import Any

from app.integrations.detection.base import (
    DetectionRateLimitError,
    DetectionProviderUnavailableError,
    DetectionTimeoutError,
)
from app.integrations.embeddings.base import (
    EmbeddingRateLimitError,
    EmbeddingProviderUnavailableError,
)
from app.integrations.generation.base import (
    GenerationRateLimitError,
    GenerationProviderUnavailableError,
    GenerationTimeoutError,
)
from app.integrations.sources.base import (
    SourceProviderRateLimitError,
    SourceProviderTimeoutError,
    SourceProviderUnavailableError,
)
from app.integrations.translation.base import (
    TranslationRateLimitError,
    TranslationProviderUnavailableError,
    TranslationTimeoutError,
)

_RETRYABLE = (
    GenerationRateLimitError,
    GenerationProviderUnavailableError,
    GenerationTimeoutError,
    EmbeddingRateLimitError,
    EmbeddingProviderUnavailableError,
    TranslationRateLimitError,
    TranslationProviderUnavailableError,
    TranslationTimeoutError,
    DetectionRateLimitError,
    DetectionProviderUnavailableError,
    DetectionTimeoutError,
    SourceProviderRateLimitError,
    SourceProviderTimeoutError,
    SourceProviderUnavailableError,
)


class FallbackProvider:
    """Invoke providers in order; only transient failures advance the chain."""

    def __init__(self, providers: tuple[Any, ...]) -> None:
        if not providers:
            raise ValueError("at least one provider is required")
        self._providers = providers
        self.provider_name = str(
            getattr(providers[0], "provider_name", "unknown")
        )
        self.model_name = str(
            getattr(providers[0], "model_name", "unknown")
        )

    @property
    def providers(self) -> tuple[Any, ...]:
        return self._providers

    def __getattr__(self, name: str) -> Any:
        # Provider capability metadata (dimensions, limits, etc.) is
        # delegated to the primary provider.
        return getattr(self._providers[0], name)

    def _call(self, method: str, *args: Any, **kwargs: Any) -> Any:
        last_error: BaseException | None = None
        for provider in self._providers:
            try:
                return getattr(provider, method)(*args, **kwargs)
            except _RETRYABLE as exc:
                last_error = exc
        if last_error is not None:
            raise last_error
        raise RuntimeError("provider fallback chain exhausted")

    def generate(self, **kwargs: Any) -> Any:
        return self._call("generate", **kwargs)

    def embed_documents(self, texts: Any) -> Any:
        return self._call("embed_documents", texts)

    def embed_query(self, text: str) -> Any:
        return self._call("embed_query", text)

    def translate(self, **kwargs: Any) -> Any:
        return self._call("translate", **kwargs)

    def detect(self, *, text: str) -> Any:
        return self._call("detect", text=text)

    def search(self, **kwargs: Any) -> Any:
        return self._call("search", **kwargs)


__all__ = ["FallbackProvider"]
