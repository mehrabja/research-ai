"""Persistent refresh sessions."""
from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import AuthenticationRequired
from app.db.models.auth_security import AuthSession


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def create_session(
    db: Session,
    *,
    user_id: uuid.UUID,
    user_agent: str | None,
    ip_address: str | None,
) -> tuple[AuthSession, str, str]:
    settings = get_settings()
    refresh_token = secrets.token_urlsafe(48)
    csrf_token = secrets.token_urlsafe(32)
    now = datetime.now(UTC)
    row = AuthSession(
        user_id=user_id,
        token_hash=_hash(refresh_token),
        csrf_token_hash=_hash(csrf_token),
        expires_at=now
        + timedelta(days=settings.jwt_refresh_token_expire_days),
        last_seen_at=now,
        user_agent=(user_agent or "")[:500] or None,
        ip_hash=_hash(ip_address) if ip_address else None,
    )
    db.add(row)
    db.flush()
    return row, refresh_token, csrf_token


def resolve_session(
    db: Session,
    *,
    refresh_token: str,
    csrf_token: str | None,
) -> AuthSession:
    settings = get_settings()
    row = db.execute(
        select(AuthSession)
        .where(AuthSession.token_hash == _hash(refresh_token))
        .with_for_update()
    ).scalar_one_or_none()
    now = datetime.now(UTC)
    if (
        row is None
        or row.revoked_at is not None
        or row.expires_at <= now
    ):
        raise AuthenticationRequired()

    if settings.auth_refresh_require_csrf:
        if not csrf_token or not secrets.compare_digest(
            row.csrf_token_hash,
            _hash(csrf_token),
        ):
            raise AuthenticationRequired("CSRF validation failed.")

    row.last_seen_at = now
    db.flush()
    return row


def revoke_session(
    db: Session,
    *,
    user_id: uuid.UUID,
    session_id: uuid.UUID,
) -> None:
    row = db.execute(
        select(AuthSession)
        .where(
            AuthSession.id == session_id,
            AuthSession.user_id == user_id,
        )
        .with_for_update()
    ).scalar_one_or_none()
    if row is None:
        raise AuthenticationRequired()
    row.revoked_at = datetime.now(UTC)
    db.commit()


def revoke_by_refresh_token(
    db: Session,
    *,
    refresh_token: str,
) -> None:
    row = db.execute(
        select(AuthSession)
        .where(AuthSession.token_hash == _hash(refresh_token))
        .with_for_update()
    ).scalar_one_or_none()
    if row is None:
        return
    if row.revoked_at is None:
        row.revoked_at = datetime.now(UTC)
    db.commit()
