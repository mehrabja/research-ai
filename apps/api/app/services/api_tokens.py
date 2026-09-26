"""Personal API token service."""
from __future__ import annotations
import hashlib
import secrets
import uuid
from datetime import UTC, datetime
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.exceptions import AuthenticationRequired
from app.db.models.api_token import ApiToken

def _sha(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()

def create_token(db: Session, *, user_id: uuid.UUID, label: str, expires_at: datetime | None) -> tuple[ApiToken, str]:
    raw = "rai_" + secrets.token_urlsafe(32)
    row = ApiToken(user_id=user_id, token_hash=_sha(raw), token_prefix=raw[:12], label=label.strip(), expires_at=expires_at)
    db.add(row)
    db.flush()
    return row, raw

def resolve_token(db: Session, *, raw: str) -> ApiToken:
    row = db.execute(select(ApiToken).where(ApiToken.token_hash == _sha(raw)).with_for_update()).scalar_one_or_none()
    now = datetime.now(UTC)
    if row is None or row.revoked_at is not None or (row.expires_at is not None and row.expires_at <= now):
        raise AuthenticationRequired()
    row.last_used_at = now
    db.commit()
    return row

def revoke_token(db: Session, *, user_id: uuid.UUID, token_id: uuid.UUID) -> None:
    row = db.execute(select(ApiToken).where(ApiToken.id == token_id, ApiToken.user_id == user_id).with_for_update()).scalar_one_or_none()
    if row is None:
        raise AuthenticationRequired()
    row.revoked_at = datetime.now(UTC)
    db.commit()
