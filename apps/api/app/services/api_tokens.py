"""Personal API token lifecycle."""
from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models.security import APIToken

def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_token(
    db: Session,
    *,
    user_id: uuid.UUID,
    name: str,
    scopes: list[str],
    expires_days: int | None,
) -> tuple[APIToken, str]:
    raw = "rai_" + secrets.token_urlsafe(32)
    expires_at = None
    if expires_days is not None:
        expires_at = datetime.now(UTC) + timedelta(days=expires_days)
    row = APIToken(
        user_id=user_id,
        name=name.strip(),
        token_prefix=raw[:12],
        token_hash=_hash(raw),
        scopes=scopes,
        expires_at=expires_at,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row, raw


def list_tokens(
    db: Session,
    *,
    user_id: uuid.UUID,
) -> list[APIToken]:
    return list(
        db.execute(
            select(APIToken)
            .where(APIToken.user_id == user_id)
            .order_by(APIToken.created_at.desc())
        ).scalars().all()
    )


def revoke_token(
    db: Session,
    *,
    user_id: uuid.UUID,
    token_id: uuid.UUID,
) -> bool:
    row = db.execute(
        select(APIToken)
        .where(
            APIToken.id == token_id,
            APIToken.user_id == user_id,
            APIToken.revoked_at.is_(None),
        )
        .with_for_update()
    ).scalar_one_or_none()
    if row is None:
        return False
    row.revoked_at = datetime.now(UTC)
    db.commit()
    return True


def authenticate_token(
    db: Session,
    *,
    raw_token: str,
) -> APIToken | None:
    if not raw_token:
        return None
    row = db.execute(
        select(APIToken).where(
            APIToken.token_hash == _hash(raw_token),
            APIToken.revoked_at.is_(None),
        )
    ).scalar_one_or_none()
    if row is None:
        return None
    if row.expires_at is not None and row.expires_at <= datetime.now(UTC):
        return None
    row.last_used_at = datetime.now(UTC)
    db.flush()
    return row
