from __future__ import annotations

from typing import Protocol


class EmailProvider(Protocol):
    provider_name: str

    def send(
        self,
        *,
        to: str,
        subject: str,
        html: str,
        idempotency_key: str | None = None,
    ) -> str:
        """Send an email and return the provider message ID."""
