"""Authentication routes, session refresh, verification and password reset."""
from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_client_ip, get_current_user
from app.core.config import get_settings
from app.core.exceptions import (
    AuthenticationRateLimited,
    AuthenticationRequired,
    InvalidCredentials,
)
from app.core.security import create_access_token, hash_password
from app.db.models.auth_security import TwoFactorAuth
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.schemas.auth_security import (
    EmailVerificationRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    RefreshResponse,
)
from app.services import auth_sessions, auth_tokens, email as email_service
from app.services.auth import (
    authenticate_user,
    get_user_by_email,
    register_user,
)
from app.services.rate_limit import get_login_rate_limiter
from app.services import two_factor as two_factor_service


router = APIRouter(prefix="/auth", tags=["auth"])


def _set_session_cookies(
    response: Response,
    *,
    refresh_token: str,
    csrf_token: str,
) -> None:
    settings = get_settings()
    max_age = settings.jwt_refresh_token_expire_days * 86400

    response.set_cookie(
        settings.auth_refresh_cookie_name,
        refresh_token,
        httponly=True,
        secure=settings.auth_refresh_secure_cookie,
        samesite=settings.auth_refresh_same_site,
        path="/",
        max_age=max_age,
    )
    response.set_cookie(
        settings.auth_csrf_cookie_name,
        csrf_token,
        httponly=False,
        secure=settings.auth_refresh_secure_cookie,
        samesite=settings.auth_refresh_same_site,
        path="/",
        max_age=max_age,
    )


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(
    payload: RegisterRequest,
    db: Session = Depends(get_db),
) -> User:
    user = register_user(
        db,
        email=payload.email,
        password=payload.password,
    )
    raw_token = auth_tokens.issue_token(
        db,
        user_id=user.id,
        token_type="email_verification",
    )
    db.commit()

    try:
        email_service.send_verification(
            to=user.email,
            token=raw_token,
        )
    except Exception:
        # Account creation remains durable. Delivery can be retried later.
        db.rollback()

    return user


@router.post(
    "/login",
    response_model=TokenResponse,
)
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
        two_factor = db.execute(
            select(TwoFactorAuth).where(
                TwoFactorAuth.user_id == user.id
            )
        ).scalar_one_or_none()
        if two_factor is not None and two_factor.enabled:
            if not payload.two_factor_code:
                raise InvalidCredentials(
                    "Two-factor authentication code required."
                )
            secret = two_factor_service.decrypt_secret(
                two_factor.secret_ciphertext
            )
            if not two_factor_service.verify_code(
                secret,
                payload.two_factor_code,
            ):
                raise InvalidCredentials(
                    "Invalid two-factor authentication code."
                )
    except InvalidCredentials:
        limiter.record_failure(email_key, ip_key)
        raise
    else:
        limiter.record_success(email_key)

    settings = get_settings()
    access_token = create_access_token(subject=str(user.id))
    _, refresh_token, csrf_token = auth_sessions.create_session(
        db,
        user_id=user.id,
        user_agent=request.headers.get("user-agent"),
        ip_address=(
            request.client.host if request.client is not None else None
        ),
    )
    db.commit()

    response.set_cookie(
        "research_ai_access_token",
        access_token,
        httponly=True,
        secure=settings.auth_refresh_secure_cookie,
        samesite=settings.auth_refresh_same_site,
        path="/",
        max_age=settings.jwt_access_token_expire_minutes * 60,
    )
    _set_session_cookies(
        response,
        refresh_token=refresh_token,
        csrf_token=csrf_token,
    )

    return TokenResponse(
        access_token=access_token,
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )


@router.get("/me", response_model=UserResponse)
def me(
    current_user: User = Depends(get_current_user),
) -> User:
    return current_user


@router.post("/refresh", response_model=RefreshResponse)
def refresh(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> RefreshResponse:
    settings = get_settings()
    refresh_token = request.cookies.get(
        settings.auth_refresh_cookie_name
    )
    csrf_token = request.headers.get("X-CSRF-Token")

    if not refresh_token:
        raise AuthenticationRequired()

    session = auth_sessions.resolve_session(
        db,
        refresh_token=refresh_token,
        csrf_token=csrf_token,
    )
    access_token = create_access_token(
        subject=str(session.user_id)
    )
    db.commit()

    response.set_cookie(
        "research_ai_access_token",
        access_token,
        httponly=True,
        secure=settings.auth_refresh_secure_cookie,
        samesite=settings.auth_refresh_same_site,
        path="/",
        max_age=settings.jwt_access_token_expire_minutes * 60,
    )

    return RefreshResponse(
        access_token=access_token,
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
)
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> None:
    settings = get_settings()
    refresh_token = request.cookies.get(
        settings.auth_refresh_cookie_name
    )
    csrf_token = request.headers.get("X-CSRF-Token")

    if refresh_token:
        if settings.auth_refresh_require_csrf and not csrf_token:
            raise AuthenticationRequired("CSRF token required.")
        session = auth_sessions.resolve_session(
            db,
            refresh_token=refresh_token,
            csrf_token=csrf_token,
        )
        session.revoked_at = datetime.now(UTC)
        db.commit()

    for name in (
        settings.auth_refresh_cookie_name,
        settings.auth_csrf_cookie_name,
        "research_ai_access_token",
    ):
        response.delete_cookie(name, path="/")


@router.post(
    "/password-reset/request",
    status_code=status.HTTP_202_ACCEPTED,
)
def password_reset_request(
    payload: PasswordResetRequest,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    user = get_user_by_email(db, payload.email)
    if user is None:
        return {"status": "accepted"}

    raw_token = auth_tokens.issue_token(
        db,
        user_id=user.id,
        token_type="password_reset",
    )
    db.commit()

    try:
        email_service.send_password_reset(
            to=user.email,
            token=raw_token,
        )
    except Exception:
        db.rollback()

    return {"status": "accepted"}


@router.post(
    "/password-reset/confirm",
    status_code=status.HTTP_204_NO_CONTENT,
)
def password_reset_confirm(
    payload: PasswordResetConfirm,
    db: Session = Depends(get_db),
) -> None:
    user_id = auth_tokens.consume_token(
        db,
        raw_token=payload.token,
        token_type="password_reset",
    )
    user = db.get(User, user_id)
    if user is None:
        raise AuthenticationRequired()

    user.password_hash = hash_password(payload.new_password)
    db.commit()


@router.post(
    "/verify-email",
    status_code=status.HTTP_204_NO_CONTENT,
)
def verify_email(
    payload: EmailVerificationRequest,
    db: Session = Depends(get_db),
) -> None:
    user_id = auth_tokens.consume_token(
        db,
        raw_token=payload.token,
        token_type="email_verification",
    )
    user = db.get(User, user_id)
    if user is None:
        raise AuthenticationRequired()

    user.email_verified_at = datetime.now(UTC)
    db.commit()
