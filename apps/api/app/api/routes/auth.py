"""Authentication routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_client_ip, get_current_user
from app.core.exceptions import (
    AuthenticationRateLimited,
    InvalidCredentials,
)
from app.core.security import create_access_token
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
