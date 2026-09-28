from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.db.models.api_token import APIToken


class APITokenInvalid(AppError):
    code = "API_TOKEN_INVALID"
    status_code = 401
    message = "API token is invalid or expired."


def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def create_token(
    db: Session,
    *,
    user_id: uuid.UUID,
    name: str,
    expires_at,
) -> tuple[APIToken, str]:
    raw_secret = secrets.token_urlsafe(40)
    token = f"rai_{raw_secret}"
    prefix = token[:12]
    row = APIToken(
        user_id=user_id,
        name=name.strip(),
        token_prefix=prefix,
        token_hash=_hash(token),
        expires_at=expires_at,
    )
    db.add(row)
    db.flush()
    return row, token


def authenticate_api_token(
    db: Session,
    *,
    raw_token: str,
) -> uuid.UUID:
    if not raw_token.startswith("rai_"):
        raise APITokenInvalid()
    row = db.execute(
        select(APIToken).where(
            APIToken.token_hash == _hash(raw_token),
            APIToken.revoked_at.is_(None),
            (APIToken.expires_at.is_(None) | (APIToken.expires_at > datetime.now(UTC))),
        )
    ).scalar_one_or_none()
    if row is None:
        raise APITokenInvalid()
    row.last_used_at = datetime.now(UTC)
    db.flush()
    return row.user_id


def list_tokens(db: Session, *, user_id: uuid.UUID) -> list[APIToken]:
    return list(
        db.execute(
            select(APIToken)
            .where(APIToken.user_id == user_id)
            .order_by(APIToken.created_at.desc())
        ).scalars()
    )


def revoke_token(
    db: Session,
    *,
    user_id: uuid.UUID,
    token_id: uuid.UUID,
) -> None:
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
        raise APITokenInvalid()
    row.revoked_at = datetime.now(UTC)
    db.flush()
