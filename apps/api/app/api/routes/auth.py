"""Authentication, OAuth and persistent-session routes."""
from __future__ import annotations

import uuid

import jwt
from fastapi import APIRouter, Depends, Header, Request, Response, status
from fastapi.responses import RedirectResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.api.dependencies import get_client_ip, get_current_user
from app.core.config import get_settings
from app.core.exceptions import (
    AuthenticationRateLimited,
    AuthenticationRequired,
    EmailNotVerified,
    InvalidCredentials,
)
from app.core.security import create_access_token, decode_access_token
from app.db.models.security import UserTwoFactor
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.auth import (
    APITokenCreateRequest,
    APITokenCreateResponse,
    APITokenRead,
    EmailTokenRequest,
    LoginRequest,
    MessageResponse,
    PasswordResetConfirmRequest,
    PasswordResetRequest,
    RegisterRequest,
    SessionListResponse,
    SessionResponse,
    TokenResponse,
    TwoFactorConfirmRequest,
    TwoFactorDisableRequest,
    TwoFactorEnrollmentResponse,
    TwoFactorStatusResponse,
    UserResponse,
)
from app.services.api_tokens import create_token, list_tokens, revoke_token
from app.services.auth import authenticate_user, get_user_by_email, register_user
from app.services.auth_tokens import reset_password, verify_email
from app.services.email_jobs import (
    enqueue_password_reset_email,
    enqueue_verification_email,
)
from app.services.oauth import begin_oauth, complete_oauth
from app.services.rate_limit import get_login_rate_limiter
from app.services.session import (
    CSRF_COOKIE_NAME,
    REFRESH_COOKIE_NAME,
    create_session,
    list_active_sessions,
    new_csrf_token,
    revoke_all_other_sessions,
    revoke_by_refresh_token,
    revoke_session,
    rotate_session,
)
from app.services.two_factor import (
    begin_enrollment,
    confirm_enrollment,
    verify_second_factor,
)
from app.services.two_factor import disable as disable_two_factor

router = APIRouter(prefix="/auth", tags=["auth"])
_bearer = HTTPBearer(auto_error=False)


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
        raise AuthenticationRequired("CSRF validation failed.")


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
        full_name=payload.full_name,
        workspace_name=payload.workspace_name,
    )
    enqueue_verification_email(db, user_id=user.id)
    db.commit()
    return user


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

    limiter.record_success(email_key)

    settings = get_settings()
    if (
        settings.auth_require_email_verification
        and user.email_verified_at is None
    ):
        raise EmailNotVerified()

    verify_second_factor(
        db,
        user_id=user.id,
        code=payload.two_factor_code,
        recovery_code=payload.recovery_code,
    )

    session, refresh_token = create_session(
        db,
        user_id=user.id,
        user_agent=request.headers.get("user-agent"),
        ip_address=get_client_ip(request),
    )
    csrf_token = new_csrf_token()
    db.commit()

    _set_session_cookies(
        response,
        refresh_token=refresh_token,
        csrf_token=csrf_token,
    )

    return TokenResponse(
        access_token=create_access_token(subject=str(user.id), session_id=str(session.id)),
        token_type="bearer",
        session_id=session.id,
    )


@router.get("/me", response_model=UserResponse)
def me(
    current_user: User = Depends(get_current_user),
) -> User:
    return current_user


@router.post("/verify-email", response_model=UserResponse)
def verify_email_route(
    payload: EmailTokenRequest,
    db: Session = Depends(get_db),
) -> User:
    return verify_email(db, raw_token=payload.token)


@router.post("/resend-verification", response_model=MessageResponse)
def resend_verification(
    payload: PasswordResetRequest,
    db: Session = Depends(get_db),
) -> MessageResponse:
    user = get_user_by_email(db, payload.email)
    if (
        user is not None
        and user.is_active
        and user.email_verified_at is None
    ):
        enqueue_verification_email(db, user_id=user.id)
        db.commit()

    return MessageResponse(
        message=(
            "If the account exists and needs verification, "
            "an email will be sent."
        )
    )


@router.post("/password-reset/request", response_model=MessageResponse)
def request_password_reset(
    payload: PasswordResetRequest,
    db: Session = Depends(get_db),
) -> MessageResponse:
    user = get_user_by_email(db, payload.email)
    if user is not None and user.is_active:
        enqueue_password_reset_email(db, user_id=user.id)
        db.commit()

    return MessageResponse(
        message="If the account exists, a password reset email will be sent."
    )


@router.post("/password-reset/confirm", response_model=MessageResponse)
def confirm_password_reset(
    payload: PasswordResetConfirmRequest,
    db: Session = Depends(get_db),
) -> MessageResponse:
    reset_password(
        db,
        raw_token=payload.token,
        new_password=payload.new_password,
    )
    return MessageResponse(message="Password reset completed.")


@router.post("/refresh", response_model=TokenResponse)
def refresh(
    request: Request,
    response: Response,
    csrf_header: str | None = Header(
        default=None,
        alias="X-CSRF-Token",
    ),
    db: Session = Depends(get_db),
) -> TokenResponse:
    settings = get_settings()
    refresh_token = request.cookies.get(
        settings.auth_refresh_cookie_name or REFRESH_COOKIE_NAME
    )
    csrf_cookie = request.cookies.get(
        settings.auth_csrf_cookie_name or CSRF_COOKIE_NAME
    )
    _require_csrf(csrf_cookie, csrf_header)
    session, new_refresh_token = rotate_session(
        db,
        raw_refresh_token=refresh_token or "",
    )
    user = db.get(User, session.user_id)
    settings = get_settings()
    if (
        user is None
        or not user.is_active
        or (
            settings.auth_require_email_verification
            and user.email_verified_at is None
        )
    ):
        db.rollback()
        raise AuthenticationRequired()
    csrf_token = new_csrf_token()
    db.commit()

    _set_session_cookies(
        response,
        refresh_token=new_refresh_token,
        csrf_token=csrf_token,
    )
    return TokenResponse(
        access_token=create_access_token(subject=str(session.user_id), session_id=str(session.id)),
        token_type="bearer",
        session_id=session.id,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    response: Response,
    csrf_header: str | None = Header(
        default=None,
        alias="X-CSRF-Token",
    ),
    db: Session = Depends(get_db),
) -> None:
    settings = get_settings()
    refresh_token = request.cookies.get(
        settings.auth_refresh_cookie_name or REFRESH_COOKIE_NAME
    )
    csrf_cookie = request.cookies.get(
        settings.auth_csrf_cookie_name or CSRF_COOKIE_NAME
    )
    _require_csrf(csrf_cookie, csrf_header)
    revoke_by_refresh_token(
        db,
        raw_refresh_token=refresh_token or "",
    )
    db.commit()
    _clear_session_cookies(response)


@router.get("/sessions", response_model=SessionListResponse)
def sessions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SessionListResponse:
    items = list_active_sessions(
        db,
        user_id=current_user.id,
    )
    return SessionListResponse(
        items=[SessionResponse.model_validate(item) for item in items],
        total=len(items),
    )


@router.delete(
    "/sessions/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
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


@router.post(
    "/sessions/revoke-others",
    status_code=status.HTTP_204_NO_CONTENT,
)
def revoke_others(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    session_id = None
    if credentials is not None:
        try:
            payload = decode_access_token(credentials.credentials)
            sid = payload.get("sid")
            if isinstance(sid, str) and sid:
                session_id = uuid.UUID(sid)
        except (jwt.PyJWTError, ValueError, TypeError):
            session_id = None
    revoke_all_other_sessions(
        db,
        user_id=current_user.id,
        except_session_id=session_id,
    )
    db.commit()


@router.get("/oauth/{provider}/start")
def oauth_start(
    provider: str,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    return RedirectResponse(
        url=begin_oauth(db, provider=provider.lower()),
        status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    )


@router.get(
    "/oauth/{provider}/callback",
    response_model=TokenResponse,
)
def oauth_callback(
    provider: str,
    code: str,
    state: str,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> TokenResponse:
    user, refresh_token, session_id = complete_oauth(
        db,
        provider=provider.lower(),
        state=state,
        code=code,
        user_agent=request.headers.get("user-agent"),
        ip_address=get_client_ip(request),
    )
    _set_session_cookies(
        response,
        refresh_token=refresh_token,
        csrf_token=new_csrf_token(),
    )
    return TokenResponse(
        access_token=create_access_token(subject=str(user.id), session_id=str(session_id)),
        token_type="bearer",
        session_id=session_id,
    )


@router.get("/2fa", response_model=TwoFactorStatusResponse)
def get_two_factor_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TwoFactorStatusResponse:
    row = db.get(UserTwoFactor, current_user.id)
    return TwoFactorStatusResponse(
        enabled=bool(row and row.enabled_at is not None),
    )


@router.post(
    "/2fa/enroll",
    response_model=TwoFactorEnrollmentResponse,
)
def enroll_two_factor(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TwoFactorEnrollmentResponse:
    row, secret, provisioning_uri, recovery_codes = begin_enrollment(
        db,
        user_id=current_user.id,
        email=current_user.email,
    )
    db.commit()
    return TwoFactorEnrollmentResponse(
        enabled=bool(row.enabled_at),
        secret=secret,
        provisioning_uri=provisioning_uri,
        recovery_codes=recovery_codes,
    )


@router.post(
    "/2fa/confirm",
    response_model=TwoFactorStatusResponse,
)
def confirm_two_factor(
    payload: TwoFactorConfirmRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TwoFactorStatusResponse:
    confirm_enrollment(
        db,
        user_id=current_user.id,
        code=payload.code,
    )
    return TwoFactorStatusResponse(enabled=True)


@router.post(
    "/2fa/disable",
    response_model=TwoFactorStatusResponse,
)
def disable_two_factor_route(
    payload: TwoFactorDisableRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TwoFactorStatusResponse:
    disable_two_factor(
        db,
        user_id=current_user.id,
        code=payload.code,
    )
    return TwoFactorStatusResponse(enabled=False)


@router.post(
    "/api-tokens",
    response_model=APITokenCreateResponse,
)
def create_api_token(
    payload: APITokenCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> APITokenCreateResponse:
    row, raw = create_token(
        db,
        user_id=current_user.id,
        name=payload.name,
        scopes=payload.scopes,
        expires_days=payload.expires_days,
    )
    return APITokenCreateResponse(
        token=raw,
        item=APITokenRead.model_validate(row),
    )


@router.get(
    "/api-tokens",
    response_model=list[APITokenRead],
)
def list_api_tokens(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[APITokenRead]:
    return [
        APITokenRead.model_validate(item)
        for item in list_tokens(db, user_id=current_user.id)
    ]


@router.delete(
    "/api-tokens/{token_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def revoke_api_token(
    token_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    revoke_token(
        db,
        user_id=current_user.id,
        token_id=token_id,
    )


__all__ = ["router"]
