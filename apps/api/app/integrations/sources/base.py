"""Provider-agnostic source discovery contract.

Mirrors the shape of ``app/integrations/detection/base.py`` and
``app/integrations/generation/base.py``: a small protocol plus a
typed exception hierarchy. Providers never touch SQLAlchemy.
"""
from __future__ import annotations

from typing import Protocol

from app.domain.source import SourceCandidate


class SourceProviderError(Exception):
    """Base class for all provider-level source discovery errors."""


class SourceProviderTimeoutError(SourceProviderError):
    """Network timeout or unrecoverable transport failure."""


class SourceProviderRateLimitError(SourceProviderError):
    """Provider signalled rate limiting (HTTP 429)."""


class SourceProviderAuthError(SourceProviderError):
    """Missing or invalid credentials (HTTP 401/403)."""


class SourceProviderUnavailableError(SourceProviderError):
    """Provider is transiently unavailable (5xx / repeated network error)."""


class SourceProviderInvalidResponseError(SourceProviderError):
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
