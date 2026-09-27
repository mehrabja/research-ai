"""Provider-agnostic source discovery contract."""
from __future__ import annotations

from typing import Protocol

from app.domain.source import SourceCandidate
from app.integrations.base import (
    ProviderAuthenticationError,
    ProviderError,
    ProviderInvalidResponseError,
    ProviderRetryableError,
)


class SourceProviderError(ProviderError):
    """Base class for all provider-level source discovery errors."""


class SourceProviderTimeoutError(ProviderRetryableError, SourceProviderError):
    """Network timeout or unrecoverable transport failure."""


class SourceProviderRateLimitError(ProviderRetryableError, SourceProviderError):
    """Provider signalled rate limiting (HTTP 429)."""


class SourceProviderUnavailableError(ProviderRetryableError, SourceProviderError):
    """Provider is transiently unavailable."""


class SourceProviderAuthError(ProviderAuthenticationError, SourceProviderError):
    """Missing or invalid credentials (HTTP 401/403)."""


class SourceProviderInvalidResponseError(
    ProviderInvalidResponseError, SourceProviderError
):
    """Response did not match the expected schema."""


class SourceSearchProvider(Protocol):
    """Protocol implemented by source discovery providers."""

    provider_name: str

    def search(
        self,
        *,
        query: str,
        limit: int,
        year: int | None = None,
        open_access_only: bool = False,
    ) -> list[SourceCandidate]: ...


__all__ = [
    "SourceProviderAuthError",
    "SourceProviderError",
    "SourceProviderInvalidResponseError",
    "SourceProviderRateLimitError",
    "SourceProviderTimeoutError",
    "SourceProviderUnavailableError",
    "SourceSearchProvider",
]
__all__ = [
    "SourceProviderAuthError",
    "SourceProviderError",
    "SourceProviderInvalidResponseError",
    "SourceProviderRateLimitError",
    "SourceProviderTimeoutError",
    "SourceProviderUnavailableError",
    "SourceSearchProvider",
]
