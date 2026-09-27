"""Email provider factory."""
from __future__ import annotations

from app.core.config import get_settings
from app.integrations.email import (
    EmailProvider,
    EmailProviderNotConfigured,
    SMTPEmailProvider,
)


def build_email_provider() -> EmailProvider:
    settings = get_settings()
    if settings.email_provider == "smtp":
        return SMTPEmailProvider(
            host=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_username,
            password=settings.smtp_password,
            sender=settings.smtp_sender,
            use_tls=settings.smtp_use_tls,
            timeout_seconds=settings.smtp_timeout_seconds,
        )
    raise EmailProviderNotConfigured(
        "email provider is not configured"
    )
