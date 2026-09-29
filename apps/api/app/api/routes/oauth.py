from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.api.dependencies import get_client_ip, get_current_user
from app.core.exceptions import OAuthLastAuthMethod
from app.db.models.oauth_account import OAuthAccount
from app.db.session import get_db
from app.services.audit import emit_audit
from app.schemas.auth import TokenResponse
from app.schemas.oauth import OAuthCallbackRequest, OAuthStartResponse
from app.services import oauth as oauth_service

router = APIRouter(prefix="/auth/oauth", tags=["oauth"])


@router.get("/accounts")
def oauth_accounts(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict[str, str]]:
    accounts = db.execute(
        select(OAuthAccount)
        .where(OAuthAccount.user_id == current_user.id)
        .order_by(OAuthAccount.created_at.asc())
    ).scalars()
    return [
        {
            "provider": account.provider,
            "created_at": account.created_at.isoformat(),
        }
        for account in accounts
    ]


@router.get("/{provider}/start", response_model=OAuthStartResponse)
def oauth_start(
    provider: str,
    db: Session = Depends(get_db),
) -> OAuthStartResponse:
    provider = provider.strip().lower()
    if provider not in oauth_service.SUPPORTED:
        raise oauth_service.InvalidCredentials()
    resolved_state = oauth_service.make_state(provider)
    code_verifier = oauth_service.make_pkce_verifier()
    oauth_service.store_state(
        db,
        provider=provider,
        state=resolved_state,
        code_challenge=oauth_service.pkce_challenge(code_verifier),
    )
    db.commit()
    return OAuthStartResponse(
        provider=provider,
        authorization_url=oauth_service.authorization_url(
            provider,
            resolved_state,
            oauth_service.pkce_challenge(code_verifier),
        ),
        state=resolved_state,
        code_verifier=code_verifier,
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
        code_verifier=body.code_verifier,
    ):
        raise oauth_service.InvalidCredentials()
    profile = oauth_service.exchange_code(provider, body.code, body.code_verifier)
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
    provider = provider.strip().lower()
    account_count = int(
        db.execute(
            select(func.count())
            .select_from(OAuthAccount)
            .where(OAuthAccount.user_id == current_user.id)
        ).scalar_one()
    )
    if account_count <= 1:
        raise OAuthLastAuthMethod()

    result = db.execute(delete(OAuthAccount).where(
        OAuthAccount.user_id == current_user.id,
        OAuthAccount.provider == provider,
    ))
    if result.rowcount == 0:
        raise OAuthLastAuthMethod()

    current_user.security_version += 1
    emit_audit(
        "OAUTH_DISCONNECTED",
        db=db,
        user_id=str(current_user.id),
        resource_type="oauth_account",
        resource_id=provider,
        reason="user_requested",
        category="authentication",
    )
    db.commit()
