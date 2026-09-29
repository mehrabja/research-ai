from __future__ import annotations

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.db.models.api_token import APIToken
from app.security.api_scopes import DEFAULT_SCOPES, normalize_scopes


class APITokenInvalid(AppError):
    code = "API_TOKEN_INVALID"
    status_code = 401
    message = "API token is invalid or expired."


class APITokenPayloadInvalid(AppError):
    code = "API_TOKEN_PAYLOAD_INVALID"
    status_code = 422
    message = "API token configuration is invalid."


@dataclass(frozen=True)
class APITokenPrincipal:
    user_id: uuid.UUID
    token_id: uuid.UUID
    scopes: frozenset[str]
    workspace_ids: frozenset[str]
    project_ids: frozenset[str]


def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _normalize_ids(values: list[uuid.UUID] | None) -> tuple[str, ...]:
    return tuple(sorted({str(v) for v in (values or [])}))


def create_token(
    db: Session,
    *,
    user_id: uuid.UUID,
    name: str,
    expires_at,
    scopes: list[str] | None = None,
    allowed_workspace_ids: list[uuid.UUID] | None = None,
    allowed_project_ids: list[uuid.UUID] | None = None,
) -> tuple[APIToken, str]:
    try:
        normalized_scopes = normalize_scopes(scopes or DEFAULT_SCOPES)
    except ValueError as exc:
        raise APITokenPayloadInvalid(str(exc)) from exc

    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if expires_at is not None and expires_at <= datetime.now(UTC):
        raise APITokenPayloadInvalid("expires_at must be in the future")

    raw_secret = secrets.token_urlsafe(40)
    token = f"rai_{raw_secret}"
    row = APIToken(
        user_id=user_id,
        name=name.strip(),
        token_prefix=token[:12],
        token_hash=_hash(token),
        expires_at=expires_at,
        scopes=list(normalized_scopes),
        allowed_workspace_ids=list(_normalize_ids(allowed_workspace_ids)),
        allowed_project_ids=list(_normalize_ids(allowed_project_ids)),
    )
    db.add(row)
    db.flush()
    return row, token


def authenticate_api_token(
    db: Session,
    *,
    raw_token: str,
) -> APITokenPrincipal:
    if not raw_token.startswith("rai_") or len(raw_token) < 20:
        raise APITokenInvalid()

    row = db.execute(
        select(APIToken)
        .where(
            APIToken.token_hash == _hash(raw_token),
            APIToken.revoked_at.is_(None),
            (APIToken.expires_at.is_(None) | (APIToken.expires_at > datetime.now(UTC))),
        )
        .with_for_update()
    ).scalar_one_or_none()
    if row is None:
        raise APITokenInvalid()

    try:
        scopes = frozenset(normalize_scopes(row.scopes or DEFAULT_SCOPES))
    except ValueError as exc:
        raise APITokenInvalid() from exc

    row.last_used_at = datetime.now(UTC)
    db.flush()

    return APITokenPrincipal(
        user_id=row.user_id,
        token_id=row.id,
        scopes=scopes,
        workspace_ids=frozenset(str(x) for x in (row.allowed_workspace_ids or [])),
        project_ids=frozenset(str(x) for x in (row.allowed_project_ids or [])),
    )


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
