"""Password-reset and email-verification token service."""
from __future__ import annotations
import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.core.exceptions import AuthenticationRequired
from app.db.models.auth import AuthToken

def _sha(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()

def issue(db: Session, *, user_id: uuid.UUID, token_type: str) -> tuple[AuthToken, str]:
    if token_type not in ("password_reset", "email_verification"):
        raise ValueError("invalid token type")
    settings = get_settings()
    raw = secrets.token_urlsafe(48)
    ttl = timedelta(minutes=settings.auth_password_reset_ttl_minutes) if token_type == "password_reset" else timedelta(hours=settings.auth_email_verification_ttl_hours)
    row = AuthToken(user_id=user_id, token_hash=_sha(raw), token_type=token_type, expires_at=datetime.now(UTC) + ttl)
    db.add(row)
    db.flush()
    return row, raw

def consume(db: Session, *, raw: str, token_type: str) -> uuid.UUID:
    row = db.execute(select(AuthToken).where(AuthToken.token_hash == _sha(raw), AuthToken.token_type == token_type).with_for_update()).scalar_one_or_none()
    now = datetime.now(UTC)
    if row is None or row.used_at is not None or row.expires_at <= now:
        raise AuthenticationRequired("Invalid or expired token.")
    row.used_at = now
    db.flush()
    return row.user_id
