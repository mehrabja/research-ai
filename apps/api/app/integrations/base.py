"""Cross-capability provider error contract."""
from __future__ import annotations


class ProviderError(Exception):
    """Base exception for all provider-level failures."""


class ProviderRetryableError(ProviderError):
    """Provider failure that may safely advance fallback routing."""


class ProviderAuthenticationError(ProviderError):
    """Credentials are missing, invalid, or rejected."""


class ProviderInvalidRequestError(ProviderError):
    """Provider rejected a request as invalid."""


class ProviderInvalidResponseError(ProviderError):
    """Provider returned malformed or inconsistent data."""


class ProviderInputTooLargeError(ProviderError):
    """Input exceeds provider limits."""


__all__ = [
    "ProviderAuthenticationError",
    "ProviderError",
    "ProviderInputTooLargeError",
    "ProviderInvalidRequestError",
    "ProviderInvalidResponseError",
    "ProviderRetryableError",
]
