"""Provider contract + typed errors for embedding integrations."""
from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from app.domain.embeddings import EmbeddingBatchResult


class EmbeddingProviderError(Exception):
    """Base for provider failures. Mapped to AppError by services."""


class EmbeddingRateLimitError(EmbeddingProviderError):
    """Provider rate-limited the request (retryable)."""


class EmbeddingProviderUnavailableError(EmbeddingProviderError):
    """Provider returned 5xx / network error (retryable)."""


class EmbeddingTimeoutError(EmbeddingProviderError):
    """Provider request timed out (retryable)."""


class EmbeddingAuthenticationError(EmbeddingProviderError):
    """Invalid API key / forbidden (non-retryable)."""


class EmbeddingInvalidRequestError(EmbeddingProviderError):
    """Provider rejected the request as invalid (non-retryable)."""


class EmbeddingInvalidResponseError(EmbeddingProviderError):
    """Provider returned malformed or inconsistent response."""


class EmbeddingInputTooLargeError(EmbeddingProviderError):
    """Per-item or per-request input exceeds provider limit."""


class EmbeddingProvider(Protocol):
    provider_name: str
    model_name: str
    dimensions: int

    # Provider-authoritative limits.
    max_batch_size: int
    max_input_tokens_per_item: int | None
    max_input_tokens_per_request: int | None

    def estimate_input_tokens(self, text: str) -> int | None:
        """Return token count, or ``None`` if not resolvable for this
        model without a live provider call."""
        ...

    def embed_documents(
        self, texts: Sequence[str]
    ) -> EmbeddingBatchResult: ...

    def embed_query(self, text: str) -> list[float]: ...


__all__ = [
    "EmbeddingAuthenticationError",
    "EmbeddingInputTooLargeError",
    "EmbeddingInvalidRequestError",
    "EmbeddingInvalidResponseError",
    "EmbeddingProvider",
    "EmbeddingProviderError",
    "EmbeddingProviderUnavailableError",
    "EmbeddingRateLimitError",
]
