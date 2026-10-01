"""FastAPI dependencies shared across routes."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AuthenticationRequired
from app.core.security import decode_access_token
from app.db.models.session import UserSession
from app.db.models.user import User
from app.db.session import get_db
from app.services.api_tokens import authenticate_token

_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise AuthenticationRequired()

    if credentials.scheme.lower() != "bearer":
        raise AuthenticationRequired()

    if not credentials.credentials:
        raise AuthenticationRequired()

    try:
        payload = decode_access_token(credentials.credentials)
    except jwt.PyJWTError:
        token = authenticate_token(db, raw_token=credentials.credentials)
        if token is None:
            raise AuthenticationRequired()
        user = db.get(User, token.user_id)
        if user is None or not user.is_active:
            raise AuthenticationRequired()
        return user

    sub = payload.get("sub")

    if not isinstance(sub, str) or not sub:
        raise AuthenticationRequired()

    try:
        user_id = uuid.UUID(sub)
    except (ValueError, TypeError):
        raise AuthenticationRequired()

    sid = payload.get("sid")
    if sid is not None:
        if not isinstance(sid, str):
            raise AuthenticationRequired()
        try:
            session_id = uuid.UUID(sid)
        except (ValueError, TypeError):
            raise AuthenticationRequired()

        session = db.execute(
            select(UserSession).where(
                UserSession.id == session_id,
                UserSession.user_id == user_id,
                UserSession.revoked_at.is_(None),
                UserSession.expires_at > datetime.now(UTC),
            )
        ).scalar_one_or_none()
        if session is None:
            raise AuthenticationRequired()

    user = db.get(User, user_id)

    if user is None or not user.is_active:
        raise AuthenticationRequired()

    return user


def get_client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"
