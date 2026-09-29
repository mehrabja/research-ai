from __future__ import annotations

import hashlib
import hmac
import secrets
import time
import urllib.parse
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import InvalidCredentials
from app.core.security import create_access_token, hash_password
from app.db.models.oauth_account import OAuthAccount
from app.db.models.oauth_state import OAuthState
from app.db.models.user import User
from app.services.auth import create_refresh_session, get_user_by_email


SUPPORTED = {"google", "github"}


def _state_signature(provider: str, nonce: str) -> str:
    secret = get_settings().jwt_secret_key.encode()
    payload = f"{provider}:{nonce}".encode()
    return hmac.new(secret, payload, hashlib.sha256).hexdigest()


def make_state(provider: str) -> str:
    nonce = secrets.token_urlsafe(24)
    issued_at = str(int(time.time()))
    payload = f"{provider}:{issued_at}:{nonce}".encode()
    signature = hmac.new(
        get_settings().jwt_secret_key.encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()
    return f"{provider}.{issued_at}.{nonce}.{signature}"


def verify_state(provider: str, state: str) -> bool:
    try:
        state_provider, issued_at_raw, nonce, signature = state.split(".", 3)
        issued_at = int(issued_at_raw)
    except (ValueError, TypeError):
        return False
    if state_provider != provider:
        return False
    if abs(int(time.time()) - issued_at) > 600:
        return False
    payload = f"{provider}:{issued_at}:{nonce}".encode("utf-8")
    expected = hmac.new(
        get_settings().jwt_secret_key.encode("utf-8"),
        payload,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def store_state(db: Session, *, provider: str, state: str) -> OAuthState:
    from datetime import UTC, datetime, timedelta

    row = OAuthState(
        provider=provider,
        state_hash=hashlib.sha256(state.encode("utf-8")).hexdigest(),
        expires_at=datetime.now(UTC) + timedelta(minutes=10),
    )
    db.add(row)
    db.flush()
    return row


def consume_state(db: Session, *, provider: str, state: str) -> bool:
    from datetime import UTC, datetime

    digest = hashlib.sha256(state.encode("utf-8")).hexdigest()
    row = db.execute(
        select(OAuthState)
        .where(
            OAuthState.provider == provider,
            OAuthState.state_hash == digest,
            OAuthState.consumed_at.is_(None),
            OAuthState.expires_at > datetime.now(UTC),
        )
        .with_for_update()
    ).scalar_one_or_none()
    if row is None:
        return False
    row.consumed_at = datetime.now(UTC)
    db.flush()
    return True

def authorization_url(provider: str, state: str) -> str:
    settings = get_settings()
    if provider == "google":
        params = {
            "client_id": settings.google_oauth_client_id,
            "redirect_uri": settings.google_oauth_redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "access_type": "offline",
            "prompt": "select_account",
        }
        return "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(params)
    if provider == "github":
        params = {
            "client_id": settings.github_oauth_client_id,
            "redirect_uri": settings.github_oauth_redirect_uri,
            "scope": "read:user user:email",
            "state": state,
        }
        return "https://github.com/login/oauth/authorize?" + urllib.parse.urlencode(params)
    raise InvalidCredentials()


def _exchange_google(code: str) -> dict[str, Any]:
    settings = get_settings()
    response = httpx.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": settings.google_oauth_client_id,
            "client_secret": settings.google_oauth_client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": settings.google_oauth_redirect_uri,
        },
        timeout=20,
    )
    response.raise_for_status()
    tokens = response.json()
    access = tokens.get("access_token")
    if not isinstance(access, str):
        raise InvalidCredentials()
    userinfo = httpx.get(
        "https://openidconnect.googleapis.com/v1/userinfo",
        headers={"Authorization": f"Bearer {access}"},
        timeout=20,
    )
    userinfo.raise_for_status()
    profile = userinfo.json()
    return {
        "provider_user_id": profile.get("sub"),
        "email": profile.get("email"),
        "email_verified": bool(profile.get("email_verified")),
    }


def _exchange_github(code: str) -> dict[str, Any]:
    settings = get_settings()
    response = httpx.post(
        "https://github.com/login/oauth/access_token",
        headers={"Accept": "application/json"},
        data={
            "client_id": settings.github_oauth_client_id,
            "client_secret": settings.github_oauth_client_secret,
            "code": code,
            "redirect_uri": settings.github_oauth_redirect_uri,
        },
        timeout=20,
    )
    response.raise_for_status()
    tokens = response.json()
    access = tokens.get("access_token")
    if not isinstance(access, str):
        raise InvalidCredentials()
    profile = httpx.get(
        "https://api.github.com/user",
        headers={
            "Authorization": f"Bearer {access}",
            "Accept": "application/vnd.github+json",
        },
        timeout=20,
    )
    profile.raise_for_status()
    data = profile.json()
    email = data.get("email")
    if not email:
        emails = httpx.get(
            "https://api.github.com/user/emails",
            headers={
                "Authorization": f"Bearer {access}",
                "Accept": "application/vnd.github+json",
            },
            timeout=20,
        )
        emails.raise_for_status()
        for item in emails.json() or []:
            if item.get("primary") and item.get("verified"):
                email = item.get("email")
                break
    return {
        "provider_user_id": data.get("id"),
        "email": email,
        "email_verified": True,
    }


def exchange_code(provider: str, code: str) -> dict[str, Any]:
    if provider == "google":
        return _exchange_google(code)
    if provider == "github":
        return _exchange_github(code)
    raise InvalidCredentials()


def login_or_create_oauth_user(
    db: Session,
    *,
    provider: str,
    profile: dict[str, Any],
    ip_address: str | None,
    user_agent: str | None,
) -> tuple[User, str, str]:
    provider_user_id = profile.get("provider_user_id")
    email = profile.get("email")
    if not isinstance(provider_user_id, (str, int)) or not isinstance(email, str) or not email:
        raise InvalidCredentials()

    provider_user_id = str(provider_user_id)
    account = db.execute(
        select(OAuthAccount).where(
            OAuthAccount.provider == provider,
            OAuthAccount.provider_user_id == provider_user_id,
        )
    ).scalar_one_or_none()

    user: User | None = None
    if account is not None:
        user = db.get(User, account.user_id)

    if user is None:
        user = get_user_by_email(db, email)
        if user is None:
            user = User(
                email=email,
                password_hash=hash_password(secrets.token_urlsafe(48)),
            )
            db.add(user)
            db.flush()
        account = OAuthAccount(
            user_id=user.id,
            provider=provider,
            provider_user_id=provider_user_id,
            email=email,
        )
        db.add(account)

    if bool(profile.get("email_verified")) and user.email_verified_at is None:
        from datetime import UTC, datetime
        user.email_verified_at = datetime.now(UTC)

    access = create_access_token(subject=str(user.id))
    _, refresh = create_refresh_session(
        db,
        user_id=user.id,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.commit()
    return user, access, refresh
