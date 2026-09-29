"""Authentication routes."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_client_ip, get_current_user
from app.core.auth_exceptions import RefreshTokenInvalid
from app.core.exceptions import (
    AuthenticationRateLimited,
    InvalidCredentials,
)
from app.core.mfa_exceptions import MFAInvalid, MFARequired
from app.core.security import create_access_token
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.activity import ActivityItem
from app.schemas.auth import (
    LoginRequest,
    LogoutRequest,
    MessageResponse,
    PasswordResetConfirmRequest,
    PasswordResetRequest,
    RefreshRequest,
    RegisterRequest,
    SessionResponse,
    TokenResponse,
    UserResponse,
    VerifyEmailRequest,
)
from app.services import activity as activity_service
from app.services import auth as auth_service
from app.services import mfa as mfa_service
from app.services.email import EmailDeliveryService
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
    user = auth_service.register_user(
        db,
        email=payload.email,
        password=payload.password,
    )
    # The raw token is intentionally not returned by the API. F11 email
    # delivery will send the token through the configured transactional
    # email provider.
    verification_token = auth_service.issue_email_verification_token(
        db,
        user_id=user.id,
    )
    from app.core.config import get_settings
    settings = get_settings()
    if settings.email_provider != "none":
        EmailDeliveryService().send(
            db,
            user_id=user.id,
            to_email=user.email,
            template="email_verification",
            subject="Verify your Research-AI email",
            html=(
                "<p>Verify your email address.</p>"
                f'<p><a href="{settings.web_app_base_url.rstrip("/")}/email-verify?token={verification_token}">'
                "Verify email</a></p>"
            ),
            idempotency_key=f"email-verification:{user.id}:{verification_token}",
        )
    db.commit()
    db.refresh(user)
    return user


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
        user = auth_service.authenticate_user(
            db,
            email=payload.email,
            password=payload.password,
        )
    except InvalidCredentials:
        limiter.record_failure(email_key, ip_key)
        raise
    else:
        limiter.record_success(email_key)

    if user.mfa_enabled:
        if not payload.mfa_code:
            raise MFARequired()
        valid_mfa = bool(
            user.mfa_secret
            and mfa_service.verify_code(
                user.mfa_secret,
                payload.mfa_code,
            )
        )
        if not valid_mfa:
            valid_recovery, remaining = mfa_service.consume_recovery_code(
                list(user.mfa_recovery_code_hashes or []),
                payload.mfa_code,
            )
            if valid_recovery:
                user.mfa_recovery_code_hashes = remaining
                db.commit()
            else:
                raise MFAInvalid()

    token = create_access_token(subject=str(user.id))
    _session, refresh_token = auth_service.create_refresh_session(
        db,
        user_id=user.id,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    db.commit()

    return TokenResponse(
        access_token=token,
        refresh_token=refresh_token,
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


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Rotate a persistent refresh session",
)
def refresh(
    payload: RefreshRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> TokenResponse:
    user, _session, refresh_token = auth_service.rotate_refresh_session(
        db,
        refresh_token=payload.refresh_token,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    access_token = create_access_token(subject=str(user.id))
    db.commit()
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
    )


@router.post(
    "/logout",
    response_model=MessageResponse,
    summary="Revoke the supplied refresh session",
)
def logout(
    payload: LogoutRequest,
    db: Session = Depends(get_db),
) -> MessageResponse:
    auth_service.revoke_session(
        db,
        refresh_token=payload.refresh_token,
    )
    db.commit()
    return MessageResponse(message="Signed out.")


@router.post(
    "/logout-all",
    response_model=MessageResponse,
    summary="Revoke all sessions for the authenticated user",
)
def logout_all(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MessageResponse:
    auth_service.revoke_all_sessions(
        db,
        user_id=current_user.id,
    )
    db.commit()
    return MessageResponse(message="All sessions have been revoked.")


@router.delete(
    "/sessions/{session_id}",
    response_model=MessageResponse,
    summary="Revoke one refresh session",
)
def revoke_session(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MessageResponse:
    if not auth_service.revoke_session_by_id(
        db,
        user_id=current_user.id,
        session_id=session_id,
    ):
        raise RefreshTokenInvalid()
    db.commit()
    return MessageResponse(message="Session revoked.")


@router.get(
    "/sessions",
    response_model=list[SessionResponse],
    summary="List active refresh sessions",
)
def list_sessions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[SessionResponse]:
    return [
        SessionResponse(
            id=session.id,
            created_at=session.created_at,
            expires_at=session.expires_at,
            last_used_at=session.last_used_at,
        )
        for session in auth_service.list_active_sessions(
            db,
            user_id=current_user.id,
        )
    ]


@router.get(
    "/activity",
    response_model=list[ActivityItem],
    summary="Return a safe user-facing security activity projection",
)
def activity(
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ActivityItem]:
    return [
        ActivityItem(
            id=item.id,
            event=item.event,
            summary=item.summary,
            occurred_at=item.occurred_at,
        )
        for item in activity_service.list_user_activity(
            db,
            user_id=current_user.id,
            limit=limit,
        )
    ]


@router.post(
    "/verify-email",
    response_model=UserResponse,
    summary="Verify an email address using a one-time token",
)
def verify_email(
    payload: VerifyEmailRequest,
    db: Session = Depends(get_db),
) -> User:
    user = auth_service.verify_email(
        db,
        token=payload.token,
    )
    db.commit()
    db.refresh(user)
    return user


@router.post(
    "/password-reset/request",
    response_model=MessageResponse,
    summary="Request a password reset email",
)
def request_password_reset(
    payload: PasswordResetRequest,
    db: Session = Depends(get_db),
) -> MessageResponse:
    user = auth_service.get_user_by_email(db, payload.email)
    if user is not None and user.is_active:
        reset_token = auth_service.issue_password_reset_token(
            db,
            user_id=user.id,
        )
        from app.core.config import get_settings
        settings = get_settings()
        if settings.email_provider != "none":
            EmailDeliveryService().send(
                db,
                user_id=user.id,
                to_email=user.email,
                template="password_reset",
                subject="Reset your Research-AI password",
                html=(
                    "<p>Password reset requested.</p>"
                    f'<p><a href="{settings.web_app_base_url.rstrip("/")}/password-reset/confirm?token={reset_token}">'
                    "Reset password</a></p>"
                ),
                idempotency_key=f"password-reset:{user.id}:{reset_token}",
            )
        db.commit()

    # Deliberately identical regardless of account existence.
    return MessageResponse(
        message="If the account exists, password-reset instructions will be sent."
    )


@router.post(
    "/password-reset/confirm",
    response_model=UserResponse,
    summary="Consume a password reset token and set a new password",
)
def confirm_password_reset(
    payload: PasswordResetConfirmRequest,
    db: Session = Depends(get_db),
) -> User:
    user = auth_service.reset_password(
        db,
        token=payload.token,
        new_password=payload.new_password,
    )
    db.commit()
    db.refresh(user)
    return user


@router.post(
    "/verification/resend",
    response_model=MessageResponse,
    summary="Request a new email verification token",
)
def resend_verification(
    payload: PasswordResetRequest,
    db: Session = Depends(get_db),
) -> MessageResponse:
    user = auth_service.get_user_by_email(db, payload.email)
    if user is not None and user.is_active and user.email_verified_at is None:
        verification_token = auth_service.issue_email_verification_token(
            db,
            user_id=user.id,
        )
        from app.core.config import get_settings
        settings = get_settings()
        if settings.email_provider != "none":
            EmailDeliveryService().send(
                db,
                user_id=user.id,
                to_email=user.email,
                template="email_verification",
                subject="Verify your Research-AI email",
                html=(
                    "<p>Verify your email address.</p>"
                    f'<p><a href="{settings.web_app_base_url.rstrip("/")}/email-verify?token={verification_token}">'
                    "Verify email</a></p>"
                ),
                idempotency_key=f"email-verification:{user.id}:{verification_token}",
            )
        db.commit()
    return MessageResponse(
        message="If the account requires verification, instructions will be sent."
    )
