"""Generation provider contract + typed errors."""
from __future__ import annotations

from typing import Protocol

from app.domain.generation import GenerationProviderResult


class GenerationProviderError(Exception):
    """Base for provider failures."""


class GenerationRateLimitError(GenerationProviderError):
    """Retryable."""


class GenerationProviderUnavailableError(GenerationProviderError):
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
    @property
    def provider_name(self) -> str: ...

    @property
    def model_name(self) -> str: ...

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
