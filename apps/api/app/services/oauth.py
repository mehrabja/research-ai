"""Google and GitHub OAuth identity integration."""
from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.security import create_access_token, hash_password
from app.db.models.auth_security import OAuthAccount, OAuthState
from app.db.models.user import User
from app.services.auth_sessions import create_session
from app.services.workspaces import ensure_default_workspace


class OAuthNotConfigured(AppError):
    code = "OAUTH_NOT_CONFIGURED"
    status_code = 503
    message = "OAuth provider is not configured."


class OAuthStateInvalid(AppError):
    code = "OAUTH_STATE_INVALID"
    status_code = 400
    message = "OAuth state is invalid or expired."


class OAuthProviderError(AppError):
    code = "OAUTH_PROVIDER_ERROR"
    status_code = 502
    message = "OAuth provider request failed."


def _hash_state(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _redirect_uri(provider: str) -> str:
    settings = get_settings()
    base = settings.oauth_redirect_base_url.rstrip("/")
    return f"{base}/auth/oauth/{provider}/callback"


def _client_config(provider: str) -> tuple[str, str, str, list[str]]:
    settings = get_settings()
    if provider == "google":
        if (
            not settings.oauth_google_client_id
            or not settings.oauth_google_client_secret
        ):
            raise OAuthNotConfigured()
        return (
            settings.oauth_google_client_id,
            settings.oauth_google_client_secret,
            "https://oauth2.googleapis.com/token",
            ["openid", "email", "profile"],
        )

    if provider == "github":
        if (
            not settings.oauth_github_client_id
            or not settings.oauth_github_client_secret
        ):
            raise OAuthNotConfigured()
        return (
            settings.oauth_github_client_id,
            settings.oauth_github_client_secret,
            "https://github.com/login/oauth/access_token",
            ["read:user", "user:email"],
        )

    raise OAuthNotConfigured("Unsupported OAuth provider.")


def create_authorization_url(
    db: Session,
    *,
    provider: str,
) -> str:
    client_id, _, _, scopes = _client_config(provider)
    state = secrets.token_urlsafe(32)

    db.add(
        OAuthState(
            provider=provider,
            state_hash=_hash_state(state),
            redirect_uri=_redirect_uri(provider),
            expires_at=datetime.now(UTC) + timedelta(minutes=10),
        )
    )
    db.commit()

    if provider == "google":
        params = {
            "client_id": client_id,
            "redirect_uri": _redirect_uri(provider),
            "response_type": "code",
            "scope": " ".join(scopes),
            "state": state,
            "access_type": "online",
            "prompt": "select_account",
        }
        return (
            "https://accounts.google.com/o/oauth2/v2/auth?"
            + urlencode(params)
        )

    params = {
        "client_id": client_id,
        "redirect_uri": _redirect_uri(provider),
        "scope": " ".join(scopes),
        "state": state,
    }
    return "https://github.com/login/oauth/authorize?" + urlencode(params)


def _consume_state(
    db: Session,
    *,
    provider: str,
    state: str,
) -> OAuthState:
    row = db.execute(
        select(OAuthState)
        .where(
            OAuthState.provider == provider,
            OAuthState.state_hash == _hash_state(state),
            OAuthState.used_at.is_(None),
        )
        .with_for_update()
    ).scalar_one_or_none()

    if row is None or row.expires_at <= datetime.now(UTC):
        raise OAuthStateInvalid()

    row.used_at = datetime.now(UTC)
    db.flush()
    return row


def _exchange_code(
    provider: str,
    *,
    code: str,
    redirect_uri: str,
) -> str:
    settings = get_settings()

    if provider == "google":
        url = "https://oauth2.googleapis.com/token"
        payload = {
            "code": code,
            "client_id": settings.oauth_google_client_id,
            "client_secret": settings.oauth_google_client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }
    else:
        url = "https://github.com/login/oauth/access_token"
        payload = {
            "code": code,
            "client_id": settings.oauth_github_client_id,
            "client_secret": settings.oauth_github_client_secret,
            "redirect_uri": redirect_uri,
        }

    try:
        response = httpx.post(
            url,
            data=payload,
            headers={"Accept": "application/json"},
            timeout=15,
        )
    except httpx.HTTPError as exc:
        raise OAuthProviderError(
            "OAuth token exchange failed."
        ) from exc

    if response.status_code >= 400:
        raise OAuthProviderError(
            f"OAuth token exchange returned HTTP {response.status_code}."
        )

    body = response.json()
    token = body.get("access_token") if isinstance(body, dict) else None
    if not isinstance(token, str):
        raise OAuthProviderError("OAuth provider returned no access token.")
    return token


def _google_identity(token: str) -> tuple[str, str]:
    try:
        response = httpx.get(
            "https://openidconnect.googleapis.com/v1/userinfo",
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
    except httpx.HTTPError as exc:
        raise OAuthProviderError("Google userinfo request failed.") from exc

    if response.status_code >= 400:
        raise OAuthProviderError("Google userinfo request was rejected.")

    body = response.json()
    sub = body.get("sub")
    email = body.get("email")
    if (
        not isinstance(sub, str)
        or not isinstance(email, str)
        or not body.get("email_verified")
    ):
        raise OAuthProviderError(
            "Google account does not provide a verified email."
        )
    return sub, email


def _github_identity(token: str) -> tuple[str, str]:
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }
    try:
        user_response = httpx.get(
            "https://api.github.com/user",
            headers=headers,
            timeout=15,
        )
        email_response = httpx.get(
            "https://api.github.com/user/emails",
            headers=headers,
            timeout=15,
        )
    except httpx.HTTPError as exc:
        raise OAuthProviderError("GitHub identity request failed.") from exc

    if (
        user_response.status_code >= 400
        or email_response.status_code >= 400
    ):
        raise OAuthProviderError("GitHub identity request was rejected.")

    user_body = user_response.json()
    emails = email_response.json()
    verified = [
        item for item in emails
        if isinstance(item, dict) and item.get("verified")
    ]
    primary = next(
        (
            item
            for item in verified
            if item.get("primary")
        ),
        None,
    )
    selected = primary or (verified[0] if verified else None)
    sub = user_body.get("id") if isinstance(user_body, dict) else None
    email = selected.get("email") if selected else None

    if sub is None or not isinstance(email, str):
        raise OAuthProviderError(
            "GitHub account does not provide a verified email."
        )
    return str(sub), email


def finish_callback(
    db: Session,
    *,
    provider: str,
    code: str,
    state: str,
    user_agent: str | None,
    ip_address: str | None,
) -> tuple[User, str, str, str]:
    state_row = _consume_state(
        db,
        provider=provider,
        state=state,
    )
    token = _exchange_code(
        provider,
        code=code,
        redirect_uri=state_row.redirect_uri,
    )

    if provider == "google":
        provider_user_id, email = _google_identity(token)
    else:
        provider_user_id, email = _github_identity(token)

    account = db.execute(
        select(OAuthAccount).where(
            OAuthAccount.provider == provider,
            OAuthAccount.provider_user_id == provider_user_id,
        )
    ).scalar_one_or_none()

    if account is not None:
        user = db.get(User, account.user_id)
        if user is None:
            raise OAuthProviderError("Linked account owner no longer exists.")
    else:
        user = db.execute(
            select(User).where(
                func.lower(User.email) == email.lower()
            )
        ).scalar_one_or_none()
        if user is None:
            user = User(
                email=email,
                password_hash=hash_password(
                    secrets.token_urlsafe(32)
                ),
                email_verified_at=datetime.now(UTC),
            )
            db.add(user)
            db.flush()
        elif user.email_verified_at is None:
            user.email_verified_at = datetime.now(UTC)

        db.add(
            OAuthAccount(
                user_id=user.id,
                provider=provider,
                provider_user_id=provider_user_id,
                provider_email=email,
            )
        )
        db.flush()

    ensure_default_workspace(db, user_id=user.id)
    _, refresh_token, csrf_token = create_session(
        db,
        user_id=user.id,
        user_agent=user_agent,
        ip_address=ip_address,
    )
    access_token = create_access_token(subject=str(user.id))
    db.commit()

    return user, access_token, refresh_token, csrf_token
