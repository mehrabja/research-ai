"""Transactional email orchestration."""
from __future__ import annotations

import hashlib

from app.core.config import get_settings
from app.integrations.email.resend import ResendEmailProvider
from app.integrations.email.smtp import SMTPEmailProvider


def get_email_provider():
    settings = get_settings()
    if settings.email_provider == "smtp":
        return SMTPEmailProvider()
    if settings.email_provider == "resend":
        return ResendEmailProvider()
    return None


def _token_key(prefix: str, token: str) -> str:
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    return f"{prefix}:{digest}"


def send_verification(*, to: str, token: str) -> str | None:
    provider = get_email_provider()
    if provider is None:
        return None
    base = get_settings().frontend_base_url.rstrip("/")
    url = f"{base}/verify-email?token={token}"
    return provider.send(
        to=to,
        subject="Verify your Research AI email",
        text_body=f"Verify your Research AI account: {url}",
        idempotency_key=_token_key("verify", token),
    )


def send_password_reset(*, to: str, token: str) -> str | None:
    provider = get_email_provider()
    if provider is None:
        return None
    base = get_settings().frontend_base_url.rstrip("/")
    url = f"{base}/reset-password?token={token}"
    return provider.send(
        to=to,
        subject="Reset your Research AI password",
        text_body=f"Reset your Research AI password: {url}",
        idempotency_key=_token_key("reset", token),
    )


def send_invitation(
    *,
    to: str,
    token: str,
    workspace_name: str,
) -> str | None:
    provider = get_email_provider()
    if provider is None:
        return None
    base = get_settings().frontend_base_url.rstrip("/")
    url = f"{base}/invite/{token}"
    return provider.send(
        to=to,
        subject=f"Invitation to {workspace_name}",
        text_body=(
            f"You were invited to {workspace_name} in Research AI: {url}"
        ),
        idempotency_key=_token_key("invite", token),
    )
