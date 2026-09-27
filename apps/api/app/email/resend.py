from __future__ import annotations

import httpx

from app.core.config import get_settings


class ResendEmailProvider:
    provider_name = "resend"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str = "https://api.resend.com",
        timeout_seconds: float = 20.0,
    ) -> None:
        settings = get_settings()
        self._api_key = api_key or settings.resend_api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds
        self._from = settings.email_from

    def send(
        self,
        *,
        to: str,
        subject: str,
        html: str,
        idempotency_key: str | None = None,
    ) -> str:
        if not self._api_key:
            raise RuntimeError("Resend API key is not configured")
        if not self._from:
            raise RuntimeError("EMAIL_FROM is not configured")

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        response = httpx.post(
            f"{self._base_url}/emails",
            json={
                "from": self._from,
                "to": [to],
                "subject": subject,
                "html": html,
            },
            headers=headers,
            timeout=self._timeout,
        )
        if response.status_code >= 400:
            raise RuntimeError(
                f"email provider HTTP {response.status_code}"
            )
        payload = response.json()
        message_id = payload.get("id")
        if not isinstance(message_id, str) or not message_id:
            raise RuntimeError("email provider returned no message id")
        return message_id
