"""FastAPI dependencies shared across routes."""
from __future__ import annotations

import uuid

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.exceptions import AuthenticationRequired
from app.core.security import decode_access_token
from app.db.models.user import User
from app.db.session import get_db
from app.security.authorization import (
    AuthPrincipal,
    enforce_api_token_request,
    ensure_bearer_security_version,
)
from app.services.api_tokens import APITokenInvalid, authenticate_api_token

_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    # Personal API keys are accepted through X-API-Key and are resolved
    # to the owning active user without exposing the raw secret.
    raw_api_key = request.headers.get("X-API-Key")
    if raw_api_key:
        try:
            token_principal = authenticate_api_token(db, raw_token=raw_api_key)
        except APITokenInvalid:
            raise AuthenticationRequired()
        user = db.get(User, token_principal.user_id)
        if user is None or not user.is_active or user.deleted_at is not None:
            raise AuthenticationRequired()
        principal = AuthPrincipal(
            user_id=user.id,
            auth_method="api_token",
            token_id=token_principal.token_id,
            scopes=token_principal.scopes,
            workspace_ids=token_principal.workspace_ids,
            project_ids=token_principal.project_ids,
        )
        request.state.auth_principal = principal
        enforce_api_token_request(request, db, principal)
        return user

    if credentials is None:
        raise AuthenticationRequired()

    if credentials.scheme.lower() != "bearer":
        raise AuthenticationRequired()

    if not credentials.credentials:
        raise AuthenticationRequired()

    try:
        payload = decode_access_token(credentials.credentials)
    except jwt.PyJWTError:
        raise AuthenticationRequired()

    request.state.jwt_payload = payload

    sub = payload.get("sub")
    if not isinstance(sub, str) or not sub:
        raise AuthenticationRequired()

    try:
        user_id = uuid.UUID(sub)
    except (ValueError, TypeError):
        raise AuthenticationRequired()

    user = db.get(User, user_id)
    if user is None or not user.is_active or user.deleted_at is not None:
        raise AuthenticationRequired()
    ensure_bearer_security_version(request, user)
    request.state.auth_principal = AuthPrincipal(
        user_id=user.id,
        auth_method="bearer",
    )
    return user


def get_client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"
