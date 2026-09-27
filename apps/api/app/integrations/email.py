"""Email provider abstraction and SMTP implementation."""
from __future__ import annotations

import smtplib
from dataclasses import dataclass
from email.message import EmailMessage


class EmailProviderNotConfigured(RuntimeError):
    """Email delivery cannot run because SMTP is not configured."""


class EmailProviderError(RuntimeError):
    """Email provider failed to deliver the message."""


@dataclass(frozen=True)
class EmailMessagePayload:
    to: str
    subject: str
    text: str
    html: str | None = None


class EmailProvider:
    provider_name = "abstract"

    def send(self, message: EmailMessagePayload) -> None:
        raise NotImplementedError


class SMTPEmailProvider(EmailProvider):
    provider_name = "smtp"

    def __init__(
        self,
        *,
        host: str,
        port: int,
        username: str,
        password: str,
        sender: str,
        use_tls: bool,
        timeout_seconds: float,
    ) -> None:
        if not host.strip() or not sender.strip():
            raise EmailProviderNotConfigured()
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._sender = sender
        self._use_tls = use_tls
        self._timeout = timeout_seconds

    def send(self, message: EmailMessagePayload) -> None:
        msg = EmailMessage()
        msg["From"] = self._sender
        msg["To"] = message.to
        msg["Subject"] = message.subject
        msg.set_content(message.text)
        if message.html:
            msg.add_alternative(message.html, subtype="html")

        try:
            with smtplib.SMTP(
                self._host,
                self._port,
                timeout=self._timeout,
            ) as smtp:
                if self._use_tls:
                    smtp.starttls()
                if self._username:
                    smtp.login(self._username, self._password)
                smtp.send_message(msg)
        except (OSError, smtplib.SMTPException) as exc:
            raise EmailProviderError("SMTP delivery failed") from exc
