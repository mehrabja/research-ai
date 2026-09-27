"""Authentication and persistent-session routes."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Cookie, Depends, Header, Request, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_client_ip, get_current_user
from app.core.config import get_settings
from app.core.exceptions import AuthenticationRateLimited, InvalidCredentials
from app.core.security import create_access_token
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    SessionListResponse,
    TokenResponse,
    UserResponse,
)
from app.services.auth import authenticate_user, register_user
from app.services.rate_limit import get_login_rate_limiter
from app.services.session import (
    CSRF_COOKIE_NAME,
    REFRESH_COOKIE_NAME,
    create_session,
    list_active_sessions,
    revoke_all_other_sessions,
    revoke_by_refresh_token,
    revoke_session,
    rotate_session,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_session_cookies(
    response: Response,
    *,
    refresh_token: str,
    csrf_token: str,
) -> None:
    settings = get_settings()
    response.set_cookie(
        key=settings.auth_refresh_cookie_name or REFRESH_COOKIE_NAME,
        value=refresh_token,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_samesite,
        max_age=settings.refresh_token_expire_days * 86400,
        path="/",
    )
    response.set_cookie(
        key=settings.auth_csrf_cookie_name or CSRF_COOKIE_NAME,
        value=csrf_token,
        httponly=False,
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_samesite,
        max_age=settings.refresh_token_expire_days * 86400,
        path="/",
    )


def _clear_session_cookies(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(
        key=settings.auth_refresh_cookie_name or REFRESH_COOKIE_NAME,
        path="/",
    )
    response.delete_cookie(
        key=settings.auth_csrf_cookie_name or CSRF_COOKIE_NAME,
        path="/",
    )


def _require_csrf(
    csrf_cookie: str | None,
    csrf_header: str | None,
) -> None:
    if not csrf_cookie or not csrf_header or csrf_cookie != csrf_header:
        from app.core.exceptions import AuthenticationRequired
        raise AuthenticationRequired()


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(
    payload: RegisterRequest,
    db: Session = Depends(get_db),
) -> User:
    return register_user(db, email=payload.email, password=payload.password)


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> TokenResponse:
    limiter = get_login_rate_limiter()
    email_key = f"email:{payload.email.lower()}"
    ip_key = f"ip:{get_client_ip(request)}"

    if (
        not limiter.check_email_allowed(email_key)
        or not limiter.check_ip_allowed(ip_key)
    ):
        raise AuthenticationRateLimited()

    try:
        user = authenticate_user(
            db,
            email=payload.email,
            password=payload.password,
        )
    except InvalidCredentials:
        limiter.record_failure(email_key, ip_key)
        raise
    else:
        limiter.record_success(email_key)

    session, refresh_token = create_session(
        db,
        user_id=user.id,
        user_agent=request.headers.get("user-agent"),
        ip_address=get_client_ip(request),
    )
    csrf_token = uuid.uuid4().hex + uuid.uuid4().hex
    db.commit()

    _set_session_cookies(
        response,
        refresh_token=refresh_token,
        csrf_token=csrf_token,
    )

    return TokenResponse(
        access_token=create_access_token(subject=str(user.id)),
        token_type="bearer",
        session_id=session.id,
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh(
    response: Response,
    refresh_token: str | None = Cookie(default=None, alias=REFRESH_COOKIE_NAME),
    csrf_cookie: str | None = Cookie(default=None, alias=CSRF_COOKIE_NAME),
    csrf_header: str | None = Header(default=None, alias="X-CSRF-Token"),
    db: Session = Depends(get_db),
) -> TokenResponse:
    _require_csrf(csrf_cookie, csrf_header)
    session, new_refresh = rotate_session(
        db,
        raw_refresh_token=refresh_token or "",
    )
    db.commit()
    _set_session_cookies(
        response,
        refresh_token=new_refresh,
        csrf_token=csrf_cookie or "",
    )
    return TokenResponse(
        access_token=create_access_token(subject=str(session.user_id)),
        token_type="bearer",
        session_id=session.id,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    refresh_token: str | None = Cookie(default=None, alias=REFRESH_COOKIE_NAME),
    csrf_cookie: str | None = Cookie(default=None, alias=CSRF_COOKIE_NAME),
    csrf_header: str | None = Header(default=None, alias="X-CSRF-Token"),
    db: Session = Depends(get_db),
) -> None:
    _require_csrf(csrf_cookie, csrf_header)
    if refresh_token:
        revoke_by_refresh_token(db, raw_refresh_token=refresh_token)
        db.commit()
    _clear_session_cookies(response)


@router.get("/sessions", response_model=SessionListResponse)
def sessions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SessionListResponse:
    items = list_active_sessions(db, user_id=current_user.id)
    return SessionListResponse(items=items, total=len(items))


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    revoke_session(
        db,
        user_id=current_user.id,
        session_id=session_id,
    )
    db.commit()


@router.post("/sessions/revoke-others", status_code=status.HTTP_204_NO_CONTENT)
def revoke_others(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    revoke_all_other_sessions(db, user_id=current_user.id)
    db.commit()


@router.get("/me", response_model=UserResponse)
def me(
    current_user: User = Depends(get_current_user),
) -> User:
    return current_user
