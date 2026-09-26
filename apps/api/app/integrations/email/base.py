"""Provider-neutral transactional email contract."""
from __future__ import annotations

from typing import Protocol


class EmailProviderError(Exception):
    """Base class for email adapter failures."""


class EmailAuthenticationError(EmailProviderError):
    """Provider credentials are invalid."""


class EmailRateLimitError(EmailProviderError):
    """Provider throttled the request."""


class EmailUnavailableError(EmailProviderError):
    """Provider is temporarily unavailable."""


class EmailInvalidRequestError(EmailProviderError):
    """Provider rejected the message."""


class EmailProvider(Protocol):
    provider_name: str

    def send(
        self,
        *,
        to: str,
        subject: str,
        text_body: str,
        html_body: str | None = None,
        idempotency_key: str | None = None,
    ) -> str | None:
        """Send one transactional email."""
