"""OAuth 2.0/OIDC identity flows for Google and GitHub."""
from __future__ import annotations

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

import httpx
import jwt
from jwt import PyJWKClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import (
    AuthenticationRequired,
    OAuthNotConfigured,
    OAuthProviderError,
    OAuthStateInvalid,
)
from app.core.security import hash_password
from app.db.models.oauth import AuthIdentity, OAuthState
from app.db.models.user import User
from app.services.session import create_session

_OAUTH_PROVIDERS = {"google", "github"}
_STATE_TTL_SECONDS = 600


@dataclass(frozen=True)
class OAuthIdentity:
    provider: str
    subject: str
    email: str
    full_name: str | None
    email_verified: bool


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _configured(provider: str) -> tuple[str, str, str]:
    settings = get_settings()
    if provider == "google":
        values = (
            settings.google_oauth_client_id,
            settings.google_oauth_client_secret,
            settings.google_oauth_redirect_uri,
        )
    else:
        values = (
            settings.github_oauth_client_id,
            settings.github_oauth_client_secret,
            settings.github_oauth_redirect_uri,
        )
    if not all(x.strip() for x in values):
        raise OAuthNotConfigured(provider)
    return values


def begin_oauth(
    db: Session,
    *,
    provider: str,
) -> str:
    if provider not in _OAUTH_PROVIDERS:
        raise OAuthProviderError("unsupported OAuth provider")
    client_id, _, redirect_uri = _configured(provider)
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    expires_at = datetime.now(UTC) + timedelta(seconds=_STATE_TTL_SECONDS)
    db.add(
        OAuthState(
            provider=provider,
            state_hash=_hash(state),
            nonce_hash=_hash(nonce),
            redirect_uri=redirect_uri,
            expires_at=expires_at,
        )
    )
    db.commit()

    if provider == "google":
        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "nonce": nonce,
            "access_type": "offline",
            "prompt": "select_account",
        }
        base_url = "https://accounts.google.com/o/oauth2/v2/auth"
    else:
        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": "read:user user:email",
            "state": state,
        }
        base_url = "https://github.com/login/oauth/authorize"
    return base_url + "?" + urlencode(params)


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
            OAuthState.state_hash == _hash(state),
            OAuthState.used_at.is_(None),
        )
        .with_for_update()
    ).scalar_one_or_none()
    if row is None or row.expires_at <= datetime.now(UTC):
        raise OAuthStateInvalid()
    row.used_at = datetime.now(UTC)
    return row


def _google_identity(
    *,
    code: str,
    state_row: OAuthState,
) -> OAuthIdentity:
    client_id, client_secret, redirect_uri = _configured("google")
    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": redirect_uri,
                },
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            payload = response.json()
    except httpx.HTTPError as exc:
        raise OAuthProviderError("Google token exchange failed") from exc

    id_token = payload.get("id_token")
    if not isinstance(id_token, str) or not id_token:
        raise OAuthProviderError("Google did not return an ID token")

    try:
        jwks = PyJWKClient(
            "https://www.googleapis.com/oauth2/v3/certs",
            cache_jwk_set=True,
            lifespan=300,
        )
        signing_key = jwks.get_signing_key_from_jwt(id_token)
        claims = jwt.decode(
            id_token,
            signing_key.key,
            algorithms=["RS256"],
            audience=client_id,
            issuer=["https://accounts.google.com", "accounts.google.com"],
        )
    except jwt.PyJWTError as exc:
        raise OAuthProviderError("Google ID token verification failed") from exc

    nonce = claims.get("nonce")
    if not isinstance(nonce, str) or not hmac_compare_hash(nonce, state_row.nonce_hash):
        raise OAuthStateInvalid()

    email = claims.get("email")
    subject = claims.get("sub")
    verified = claims.get("email_verified") is True
    if not isinstance(email, str) or not isinstance(subject, str) or not verified:
        raise OAuthProviderError("Google account email is not verified")

    return OAuthIdentity(
        provider="google",
        subject=subject,
        email=email.lower(),
        full_name=claims.get("name"),
        email_verified=True,
    )


def _github_identity(
    *,
    code: str,
    state_row: OAuthState,
) -> OAuthIdentity:
    client_id, client_secret, redirect_uri = _configured("github")
    try:
        with httpx.Client(timeout=15.0) as client:
            token_response = client.post(
                "https://github.com/login/oauth/access_token",
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "code": code,
                    "redirect_uri": redirect_uri,
                },
                headers={"Accept": "application/json"},
            )
            token_response.raise_for_status()
            token = token_response.json().get("access_token")
            if not isinstance(token, str) or not token:
                raise OAuthProviderError("GitHub did not return an access token")

            api_headers = {
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
            }
            user_response = client.get(
                "https://api.github.com/user",
                headers=api_headers,
            )
            user_response.raise_for_status()
            profile = user_response.json()

            email_response = client.get(
                "https://api.github.com/user/emails",
                headers=api_headers,
            )
            email_response.raise_for_status()
            emails = email_response.json()
    except (httpx.HTTPError, OAuthProviderError) as exc:
        if isinstance(exc, OAuthProviderError):
            raise
        raise OAuthProviderError("GitHub identity lookup failed") from exc

    verified_email = next(
        (
            item.get("email")
            for item in emails
            if item.get("primary") is True and item.get("verified") is True
        ),
        None,
    )
    if not isinstance(verified_email, str):
        verified_email = next(
            (
                item.get("email")
                for item in emails
                if item.get("verified") is True
            ),
            None,
        )
    subject = profile.get("id")
    if verified_email is None or subject is None:
        raise OAuthProviderError("GitHub account has no verified email")

    return OAuthIdentity(
        provider="github",
        subject=str(subject),
        email=verified_email.lower(),
        full_name=profile.get("name") or profile.get("login"),
        email_verified=True,
    )


def hmac_compare_hash(value: str, hashed: str | None) -> bool:
    if hashed is None:
        return False
    return secrets.compare_digest(_hash(value), hashed)


def complete_oauth(
    db: Session,
    *,
    provider: str,
    state: str,
    code: str,
    user_agent: str | None,
    ip_address: str | None,
) -> tuple[User, str, uuid.UUID]:
    state_row = _consume_state(db, provider=provider, state=state)
    identity = (
        _google_identity(code=code, state_row=state_row)
        if provider == "google"
        else _github_identity(code=code, state_row=state_row)
    )

    existing_identity = db.execute(
        select(AuthIdentity)
        .where(
            AuthIdentity.provider == identity.provider,
            AuthIdentity.subject == identity.subject,
        )
        .with_for_update()
    ).scalar_one_or_none()

    if existing_identity is not None:
        user = db.get(User, existing_identity.user_id)
        if user is None or not user.is_active:
            raise AuthenticationRequired()
    else:
        user = db.execute(
            select(User)
            .where(User.email == identity.email)
            .with_for_update()
        ).scalar_one_or_none()
        if user is None:
            user = User(
                email=identity.email,
                password_hash=hash_password(secrets.token_urlsafe(32)),
                full_name=identity.full_name,
                email_verified_at=(
                    datetime.now(UTC) if identity.email_verified else None
                ),
            )
            db.add(user)
            db.flush()
        elif identity.email_verified and user.email_verified_at is None:
            user.email_verified_at = datetime.now(UTC)

        db.add(
            AuthIdentity(
                user_id=user.id,
                provider=identity.provider,
                subject=identity.subject,
                provider_email=identity.email,
            )
        )
        try:
            db.flush()
        except IntegrityError as exc:
            db.rollback()
            raise OAuthProviderError(
                "OAuth identity linking conflicted with another sign-in"
            ) from exc

    session, refresh_token = create_session(
        db,
        user_id=user.id,
        user_agent=user_agent,
        ip_address=ip_address,
    )
    db.commit()
    return user, refresh_token, session.id
