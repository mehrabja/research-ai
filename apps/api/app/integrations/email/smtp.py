"""SMTP email adapter."""
from __future__ import annotations

import smtplib
from email.message import EmailMessage

from app.core.config import get_settings
from app.integrations.email.base import EmailProviderError


class SMTPEmailProvider:
    provider_name = "smtp"

    def __init__(self) -> None:
        settings = get_settings()
        self._host = settings.smtp_host
        self._port = settings.smtp_port
        self._username = settings.smtp_username
        self._password = settings.smtp_password
        self._use_tls = settings.smtp_use_tls
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
        if not self._host or not self._sender:
            raise EmailProviderError("SMTP is not configured.")
        if not to or not subject or not text_body:
            raise EmailProviderError("Email message is incomplete.")

        message = EmailMessage()
        message["From"] = self._sender
        message["To"] = to
        message["Subject"] = subject
        message.set_content(text_body)
        if html_body:
            message.add_alternative(html_body, subtype="html")

        try:
            with smtplib.SMTP(self._host, self._port, timeout=20) as client:
                if self._use_tls:
                    client.starttls()
                if self._username:
                    client.login(self._username, self._password)
                client.send_message(message)
        except (OSError, smtplib.SMTPException) as exc:
            raise EmailProviderError("SMTP delivery failed.") from exc

        return None
