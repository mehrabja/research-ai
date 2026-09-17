"""M16 — Translation provider contract + typed errors."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class TranslationProviderError(Exception): ...


class TranslationRateLimitError(TranslationProviderError): ...


class TranslationProviderUnavailableError(TranslationProviderError): ...


class TranslationTimeoutError(TranslationProviderUnavailableError): ...


class TranslationAuthenticationError(TranslationProviderError): ...


class TranslationInvalidRequestError(TranslationProviderError): ...


class TranslationInvalidResponseError(TranslationProviderError): ...


class TranslationInputTooLargeError(TranslationProviderError): ...


@dataclass(frozen=True)
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
