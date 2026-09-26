"""M37 — Invitation domain primitives."""
from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from app.domain.membership import ROLE_ADMIN, ROLE_MEMBER, ROLE_VIEWER

# States — derived, not stored.
INVITATION_PENDING = "pending"
INVITATION_ACCEPTED = "accepted"
INVITATION_REVOKED = "revoked"
INVITATION_EXPIRED = "expired"

INVITATION_STATES: tuple[str, ...] = (
    INVITATION_PENDING,
    INVITATION_ACCEPTED,
    INVITATION_REVOKED,
    INVITATION_EXPIRED,
)

# Roles assignable via invitation. ``owner`` is deliberately excluded:
# ownership is transferred explicitly, never invited.
INVITABLE_ROLES: tuple[str, ...] = (ROLE_ADMIN, ROLE_MEMBER, ROLE_VIEWER)

DEFAULT_INVITATION_TTL_DAYS = 7
TOKEN_BYTES = 32


def generate_token() -> str:
    return secrets.token_urlsafe(TOKEN_BYTES)


def hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def default_expires_at(
    *,
    now: datetime | None = None,
    ttl_days: int = DEFAULT_INVITATION_TTL_DAYS,
) -> datetime:
    base = now or datetime.now(UTC)
    return base + timedelta(days=ttl_days)


def compute_state(
    *,
    accepted_at: datetime | None,
    revoked_at: datetime | None,
    expires_at: datetime,
    now: datetime | None = None,
) -> str:
    if accepted_at is not None:
        return INVITATION_ACCEPTED
    if revoked_at is not None:
        return INVITATION_REVOKED
    current = now or datetime.now(UTC)
    if expires_at <= current:
        return INVITATION_EXPIRED
    return INVITATION_PENDING


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def email_matches(*, invitation_email: str, user_email: str) -> bool:
    return normalize_email(invitation_email) == normalize_email(user_email)


__all__ = [
    "DEFAULT_INVITATION_TTL_DAYS",
    "INVITABLE_ROLES",
    "INVITATION_ACCEPTED",
    "INVITATION_EXPIRED",
    "INVITATION_PENDING",
    "INVITATION_REVOKED",
    "INVITATION_STATES",
    "TOKEN_BYTES",
    "compute_state",
    "default_expires_at",
    "email_matches",
    "generate_token",
    "hash_token",
    "normalize_email",
]
