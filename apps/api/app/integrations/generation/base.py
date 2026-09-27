"""Generation provider contract + typed errors."""
from __future__ import annotations

from typing import Protocol




from app.domain.generation import GenerationProviderResult
from app.integrations.base import ProviderError
from app.integrations.base import ProviderRetryableError, ProviderAuthenticationError, ProviderInvalidRequestError, ProviderInvalidResponseError, ProviderInputTooLargeError


from app.integrations.base import ProviderError, ProviderRetryableError, ProviderAuthenticationError, ProviderInvalidRequestError, ProviderInvalidResponseError, ProviderInputTooLargeError


class GenerationProviderError(ProviderError):
    """Base for provider failures."""


class GenerationRateLimitError(ProviderRetryableError, GenerationProviderError):
    """Retryable."""


class GenerationProviderUnavailableError(ProviderRetryableError, GenerationProviderError):
    """Retryable (5xx, transport)."""


class GenerationTimeoutError(GenerationProviderUnavailableError):
    """Retryable (specific timeout)."""


class GenerationAuthenticationError(GenerationProviderError):
    """Non-retryable."""


class GenerationInvalidRequestError(GenerationProviderError):
    """Non-retryable."""


class GenerationInvalidResponseError(GenerationProviderError):
    """Non-retryable."""


class GenerationInputTooLargeError(GenerationProviderError):
    """Non-retryable."""


class GenerationProvider(Protocol):
    provider_name: str
    model_name: str

    def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_output_tokens: int,
    ) -> GenerationProviderResult: ...


__all__ = [
    "GenerationAuthenticationError",
    "GenerationInputTooLargeError",
    "GenerationInvalidRequestError",
    "GenerationInvalidResponseError",
    "GenerationProvider",
    "GenerationProviderError",
    "GenerationProviderUnavailableError",
    "GenerationRateLimitError",
    "GenerationTimeoutError",
]
