"""Authentication routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy import select\nfrom sqlalchemy.orm import Session

from app.api.dependencies import get_client_ip, get_current_user
from app.core.exceptions import (
    AuthenticationRateLimited,
    InvalidCredentials,
)
from app.core.security import create_access_token\nfrom app.db.models.auth import TwoFactorAuth\nfrom app.services import auth_sessions, auth_tokens, email as email_service, two_factor
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.services.auth import authenticate_user, register_user
from app.services.rate_limit import get_login_rate_limiter

router = APIRouter(
    prefix="/auth",
    tags=["auth"],
)


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
def register(
    payload: RegisterRequest,
    db: Session = Depends(get_db),
) -> User:
    return register_user(
        db,
        email=payload.email,
        password=payload.password,
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Exchange credentials for a JWT access token",
)
def login(
    payload: LoginRequest,
    request: Request,
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

    token = create_access_token(subject=str(user.id))

    return TokenResponse(
        access_token=token,
        token_type="bearer",
    )


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Return the authenticated user",
)
def me(
    current_user: User = Depends(get_current_user),
) -> User:
    return current_user


@router.post("/refresh", response_model=TokenResponse)
def refresh(
    payload: RefreshRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> TokenResponse:
    settings = __import__("app.core.config", fromlist=["get_settings"]).get_settings()
    refresh_token = payload.refresh_token or request.cookies.get(settings.auth_refresh_cookie_name)
    csrf_token = payload.csrf_token or request.headers.get("X-CSRF-Token") or request.cookies.get(settings.auth_csrf_cookie_name)
    if not refresh_token:
        raise AuthenticationRequired()
    session = auth_sessions.resolve_session(db, refresh_token=refresh_token, csrf_token=csrf_token)
    access = create_access_token(subject=str(session.user_id))
    db.commit()
    response.set_cookie(settings.auth_refresh_cookie_name, refresh_token, httponly=True, secure=settings.auth_refresh_secure_cookie, samesite=settings.auth_refresh_same_site, path="/", max_age=settings.jwt_refresh_token_expire_days*86400)
    return TokenResponse(access_token=access, token_type="bearer", expires_in=settings.jwt_access_token_expire_minutes*60)

@router.post("/logout", status_code=204)
def logout(request: Request, response: Response, db: Session = Depends(get_db)) -> None:
    settings = __import__("app.core.config", fromlist=["get_settings"]).get_settings()
    token = request.cookies.get(settings.auth_refresh_cookie_name)
    if token:
        auth_sessions.revoke_session(db, refresh_token=token)
        db.commit()
    response.delete_cookie(settings.auth_refresh_cookie_name, path="/")
    response.delete_cookie(settings.auth_csrf_cookie_name, path="/")

@router.post("/password-reset/request", status_code=202)
def password_reset_request(payload: PasswordResetRequest, db: Session = Depends(get_db)) -> dict[str, str]:
    user = get_user_by_email(db, payload.email)
    if user is not None:
        _, token = auth_tokens.issue(db, user_id=user.id, token_type="password_reset")
        db.commit()
        try:
            email_service.send_password_reset(to=user.email, token=token)
        except Exception:
            db.rollback()
    return {"status": "accepted"}

@router.post("/password-reset/confirm", status_code=204)
def password_reset_confirm(payload: PasswordResetConfirm, db: Session = Depends(get_db)) -> None:
    user_id = auth_tokens.consume(db, raw=payload.token, token_type="password_reset")
    user = db.get(User, user_id)
    if user is None:
        raise AuthenticationRequired()
    from app.core.security import hash_password
    user.password_hash = hash_password(payload.new_password)
    db.commit()

@router.post("/verify-email", status_code=204)
def verify_email(payload: EmailVerificationRequest, db: Session = Depends(get_db)) -> None:
    user_id = auth_tokens.consume(db, raw=payload.token, token_type="email_verification")
    user = db.get(User, user_id)
    if user is None:
        raise AuthenticationRequired()
    from datetime import datetime, UTC
    user.email_verified_at = datetime.now(UTC)
    db.commit()
