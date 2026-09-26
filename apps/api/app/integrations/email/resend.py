"""Resend email adapter."""
from __future__ import annotations

import httpx

from app.core.config import get_settings
from app.integrations.email.base import (
    EmailAuthenticationError,
    EmailInvalidRequestError,
    EmailProviderError,
    EmailRateLimitError,
    EmailUnavailableError,
)


class ResendEmailProvider:
    provider_name = "resend"

    def __init__(self) -> None:
        settings = get_settings()
        self._api_key = settings.resend_api_key
        self._base_url = settings.resend_base_url.rstrip("/")
        self._sender = settings.email_from_address

    def send(
        self,
        *,
        to: str,
        subject: str,
        text_body: str,
        html_body: str | None = None,
        idempotency_key: str | None = None,
    ) -> str | None:
        if not self._api_key or not self._sender:
            raise EmailProviderError("Resend is not configured.")

        payload: dict[str, object] = {
            "from": self._sender,
            "to": [to],
            "subject": subject,
            "text": text_body,
        }
        if html_body:
            payload["html"] = html_body

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key

        try:
            response = httpx.post(
                f"{self._base_url}/emails",
                json=payload,
                headers=headers,
                timeout=20,
            )
        except httpx.HTTPError as exc:
            raise EmailUnavailableError("Email provider request failed.") from exc

        if response.status_code in (401, 403):
            raise EmailAuthenticationError("Email provider authentication failed.")
        if response.status_code == 429:
            raise EmailRateLimitError("Email provider rate limit reached.")
        if response.status_code >= 500:
            raise EmailUnavailableError("Email provider is unavailable.")
        if response.status_code >= 400:
            raise EmailInvalidRequestError("Email provider rejected the message.")

        try:
            body = response.json()
        except ValueError as exc:
            raise EmailUnavailableError("Email provider returned invalid JSON.") from exc

        message_id = body.get("id") if isinstance(body, dict) else None
        return message_id if isinstance(message_id, str) else None
