"""OAuth browser routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.schemas.auth_security import OAuthStartResponse
from app.services import oauth


router = APIRouter(prefix="/auth/oauth", tags=["oauth"])


@router.get(
    "/{provider}",
    response_model=OAuthStartResponse,
)
def start(
    provider: str,
    db: Session = Depends(get_db),
) -> OAuthStartResponse:
    return OAuthStartResponse(
        provider=provider,
        authorization_url=oauth.create_authorization_url(
            db,
            provider=provider,
        ),
    )


@router.get("/{provider}/callback")
def callback(
    provider: str,
    code: str,
    state: str,
    request: Request,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    _, access_token, refresh_token, csrf_token = oauth.finish_callback(
        db,
        provider=provider,
        code=code,
        state=state,
        user_agent=request.headers.get("user-agent"),
        ip_address=(
            request.client.host
            if request.client is not None
            else None
        ),
    )
    settings = get_settings()
    response = RedirectResponse(
        settings.frontend_base_url.rstrip("/") + "/oauth/success"
    )
    response.set_cookie(
        "research_ai_access_token",
        access_token,
        httponly=True,
        secure=settings.auth_refresh_secure_cookie,
        samesite=settings.auth_refresh_same_site,
        path="/",
        max_age=settings.jwt_access_token_expire_minutes * 60,
    )
    response.set_cookie(
        settings.auth_refresh_cookie_name,
        refresh_token,
        httponly=True,
        secure=settings.auth_refresh_secure_cookie,
        samesite=settings.auth_refresh_same_site,
        path="/",
        max_age=settings.jwt_refresh_token_expire_days * 86400,
    )
    response.set_cookie(
        settings.auth_csrf_cookie_name,
        csrf_token,
        httponly=False,
        secure=settings.auth_refresh_secure_cookie,
        samesite=settings.auth_refresh_same_site,
        path="/",
        max_age=settings.jwt_refresh_token_expire_days * 86400,
    )
    return response
