"""Detection provider contract + typed errors."""
from __future__ import annotations

from typing import Protocol

from app.domain.detection import DetectionProviderResult


class DetectionProviderError(Exception):
    """Base for provider failures."""


class DetectionRateLimitError(DetectionProviderError):
    """Retryable."""


class DetectionTimeoutError(DetectionProviderError):
    """Retryable."""


class DetectionProviderUnavailableError(DetectionProviderError):
    """Retryable (5xx, transport)."""


class DetectionAuthenticationError(DetectionProviderError):
    """Non-retryable."""


class DetectionInvalidRequestError(DetectionProviderError):
    """Non-retryable."""


class DetectionInvalidResponseError(DetectionProviderError):
    """Non-retryable."""


class DetectionInputTooLargeError(DetectionProviderError):
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
