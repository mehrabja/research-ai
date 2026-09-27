"""Detection provider contract + typed errors."""
from __future__ import annotations

from typing import Protocol

from app.domain.detection import DetectionProviderResult
from app.integrations.base import (
    ProviderAuthenticationError,
    ProviderError,
    ProviderInputTooLargeError,
    ProviderInvalidRequestError,
    ProviderInvalidResponseError,
    ProviderRetryableError,
)


class DetectionProviderError(ProviderError):
    """Base for provider failures."""


class DetectionRateLimitError(ProviderRetryableError, DetectionProviderError):
    """Retryable."""


class DetectionTimeoutError(ProviderRetryableError, DetectionProviderError):
    """Retryable."""


class DetectionProviderUnavailableError(ProviderRetryableError, DetectionProviderError):
    """Retryable (5xx, transport)."""


class DetectionAuthenticationError(ProviderAuthenticationError, DetectionProviderError):
    """Non-retryable."""


class DetectionInvalidRequestError(ProviderInvalidRequestError, DetectionProviderError):
    """Non-retryable."""


class DetectionInvalidResponseError(ProviderInvalidResponseError, DetectionProviderError):
    """Non-retryable."""


class DetectionInputTooLargeError(ProviderInputTooLargeError, DetectionProviderError):
    """Non-retryable."""


class DetectionProvider(Protocol):
    provider_name: str
    model_name: str

    def detect(self, *, text: str) -> DetectionProviderResult: ...


__all__ = [
    "DetectionAuthenticationError",
    "DetectionInputTooLargeError",
    "DetectionInvalidRequestError",
    "DetectionInvalidResponseError",
    "DetectionProvider",
    "DetectionProviderError",
    "DetectionProviderUnavailableError",
    "DetectionRateLimitError",
    "DetectionTimeoutError",
]
