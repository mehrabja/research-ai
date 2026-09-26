"""One-time password-reset and email-verification tokens."""
from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import AuthenticationRequired
from app.db.models.auth_security import AuthToken


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def issue_token(
    db: Session,
    *,
    user_id: uuid.UUID,
    token_type: str,
) -> str:
    settings = get_settings()
    if token_type == "password_reset":
        ttl = timedelta(minutes=settings.auth_password_reset_ttl_minutes)
    elif token_type == "email_verification":
        ttl = timedelta(hours=settings.auth_email_verification_ttl_hours)
    else:
        raise ValueError("unsupported auth token type")

    raw = secrets.token_urlsafe(48)
    db.add(
        AuthToken(
            user_id=user_id,
            token_hash=_hash(raw),
            token_type=token_type,
            expires_at=datetime.now(UTC) + ttl,
        )
    )
    db.flush()
    return raw


def consume_token(
    db: Session,
    *,
    raw_token: str,
    token_type: str,
) -> uuid.UUID:
    row = db.execute(
        select(AuthToken)
        .where(
            AuthToken.token_hash == _hash(raw_token),
            AuthToken.token_type == token_type,
        )
        .with_for_update()
    ).scalar_one_or_none()
    now = datetime.now(UTC)
    if row is None or row.used_at is not None or row.expires_at <= now:
        raise AuthenticationRequired("Invalid or expired token.")
    row.used_at = now
    db.flush()
    return row.user_id
