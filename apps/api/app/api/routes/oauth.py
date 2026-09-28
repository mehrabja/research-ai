from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.dependencies import get_client_ip, get_current_user
from app.db.session import get_db
from app.schemas.auth import TokenResponse
from app.schemas.oauth import OAuthCallbackRequest, OAuthStartResponse
from app.services import oauth as oauth_service

router = APIRouter(prefix="/auth/oauth", tags=["oauth"])


@router.get("/{provider}/start", response_model=OAuthStartResponse)
def oauth_start(
    provider: str,
    db: Session = Depends(get_db),
) -> OAuthStartResponse:
    provider = provider.strip().lower()
    if provider not in oauth_service.SUPPORTED:
        raise oauth_service.InvalidCredentials()
    resolved_state = oauth_service.make_state(provider)
    oauth_service.store_state(
        db,
        provider=provider,
        state=resolved_state,
    )
    db.commit()
    return OAuthStartResponse(
        provider=provider,
        authorization_url=oauth_service.authorization_url(provider, resolved_state),
        state=resolved_state,
    )


@router.post("/{provider}/callback", response_model=TokenResponse)
def oauth_callback(
    provider: str,
    body: OAuthCallbackRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> TokenResponse:
    provider = provider.strip().lower()
    if provider not in oauth_service.SUPPORTED:
        raise oauth_service.InvalidCredentials()
    if not oauth_service.verify_state(provider, body.state):
        raise oauth_service.InvalidCredentials()
    if not oauth_service.consume_state(
        db,
        provider=provider,
        state=body.state,
    ):
        raise oauth_service.InvalidCredentials()
    profile = oauth_service.exchange_code(provider, body.code)
    _user, access, refresh = oauth_service.login_or_create_oauth_user(
        db,
        provider=provider,
        profile=profile,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
    )


@router.delete("/{provider}", status_code=204)
def disconnect_oauth(
    provider: str,
    current_user=Depends(get_current_user),
    db: Session=Depends(get_db),
):
    from sqlalchemy import delete

    from app.db.models.oauth_account import OAuthAccount
    db.execute(delete(OAuthAccount).where(
        OAuthAccount.user_id == current_user.id,
        OAuthAccount.provider == provider.strip().lower(),
    ))
    db.commit()
