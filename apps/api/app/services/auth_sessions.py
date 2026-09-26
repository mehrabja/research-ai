"""Secure refresh/session service."""
from __future__ import annotations
import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.core.exceptions import AuthenticationRequired
from app.db.models.auth import AuthSession

def _sha(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()

def issue_session(db: Session, *, user_id: uuid.UUID, user_agent: str | None, ip: str | None) -> tuple[AuthSession, str, str]:
    settings = get_settings()
    raw = secrets.token_urlsafe(48)
    csrf = secrets.token_urlsafe(32)
    now = datetime.now(UTC)
    row = AuthSession(user_id=user_id, token_hash=_sha(raw), csrf_token_hash=_sha(csrf), expires_at=now + timedelta(days=settings.jwt_refresh_token_expire_days), last_seen_at=now, user_agent=(user_agent or "")[:500] or None, ip_hash=_sha(ip) if ip else None)
    db.add(row)
    db.flush()
    return row, raw, csrf

def resolve_session(db: Session, *, refresh_token: str, csrf_token: str | None = None, touch: bool = True) -> AuthSession:
    settings = get_settings()
    row = db.execute(select(AuthSession).where(AuthSession.token_hash == _sha(refresh_token)).with_for_update()).scalar_one_or_none()
    now = datetime.now(UTC)
    if row is None or row.revoked_at is not None or row.expires_at <= now:
        raise AuthenticationRequired()
    if settings.auth_refresh_require_csrf and (not csrf_token or not secrets.compare_digest(row.csrf_token_hash, _sha(csrf_token))):
        raise AuthenticationRequired("CSRF validation failed.")
    if touch:
        row.last_seen_at = now
        db.flush()
    return row

def revoke_session(db: Session, *, refresh_token: str) -> bool:
    row = db.execute(select(AuthSession).where(AuthSession.token_hash == _sha(refresh_token)).with_for_update()).scalar_one_or_none()
    if row is None or row.revoked_at is not None:
        return False
    row.revoked_at = datetime.now(UTC)
    db.flush()
    return True

def revoke_session_by_id(db: Session, *, user_id: uuid.UUID, session_id: uuid.UUID) -> None:
    row = db.execute(select(AuthSession).where(AuthSession.user_id == user_id, AuthSession.id == session_id).with_for_update()).scalar_one_or_none()
    if row is None:
        raise AuthenticationRequired()
    row.revoked_at = datetime.now(UTC)
    db.commit()

def revoke_all_sessions(db: Session, *, user_id: uuid.UUID) -> int:
    now = datetime.now(UTC)
    rows = db.execute(select(AuthSession).where(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))).scalars().all()
    for row in rows:
        row.revoked_at = now
    db.flush()
    return len(rows)
