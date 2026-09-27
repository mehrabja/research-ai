"""M16 — Translation provider contract + typed errors."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.integrations.base import (
    ProviderAuthenticationError,
    ProviderError,
    ProviderInputTooLargeError,
    ProviderInvalidRequestError,
    ProviderInvalidResponseError,
    ProviderRetryableError,
)


class TranslationProviderError(ProviderError):
    """Base translation provider error."""


class TranslationRateLimitError(ProviderRetryableError, TranslationProviderError): ...
class TranslationProviderUnavailableError(ProviderRetryableError, TranslationProviderError): ...
class TranslationTimeoutError(TranslationProviderUnavailableError): ...
class TranslationAuthenticationError(ProviderAuthenticationError, TranslationProviderError): ...
class TranslationInvalidRequestError(ProviderInvalidRequestError, TranslationProviderError): ...
class TranslationInvalidResponseError(ProviderInvalidResponseError, TranslationProviderError): ...
class TranslationInputTooLargeError(ProviderInputTooLargeError, TranslationProviderError): ...


@dataclass(frozen=True)
class TranslationProviderResult:
class TranslationProviderResult:
    translated_text: str
    provider: str
    model: str
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    request_id: str | None


class TranslationProvider(Protocol):
    provider_name: str
    model_name: str

    def translate(
        self,
        *,
        source_text: str,
        source_language: str,
        target_language: str,
        instructions: str,
        temperature: float,
        max_output_tokens: int,
    ) -> TranslationProviderResult: ...


__all__ = [
    "TranslationAuthenticationError",
    "TranslationInputTooLargeError",
    "TranslationInvalidRequestError",
    "TranslationInvalidResponseError",
    "TranslationProvider",
    "TranslationProviderError",
    "TranslationProviderResult",
    "TranslationProviderUnavailableError",
    "TranslationRateLimitError",
    "TranslationTimeoutError",
]
