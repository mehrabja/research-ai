"""Authentication service."""
from __future__ import annotations

import hashlib
import logging
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth_exceptions import (
    EmailVerificationInvalid,
    EmailVerificationRequired,
    PasswordResetInvalid,
    RefreshTokenInvalid,
)
from app.core.config import get_settings
from app.core.exceptions import InvalidCredentials, UserAlreadyExists
from app.core.security import hash_password, password_needs_rehash, verify_password
from app.db.models.auth_session import AuthSession
from app.db.models.auth_token import AuthOneTimeToken
from app.db.models.user import User

logger = logging.getLogger(__name__)

_UNIQUE_VIOLATION = "23505"
PASSWORD_RESET_PURPOSE = "password_reset"
EMAIL_VERIFICATION_PURPOSE = "email_verification"


def get_user_by_email(db: Session, email: str) -> User | None:
    stmt = select(User).where(func.lower(User.email) == email.lower())
    return db.execute(stmt).scalar_one_or_none()


def register_user(
    db: Session,
    *,
    email: str,
    password: str,
) -> User:
    if get_user_by_email(db, email) is not None:
        raise UserAlreadyExists()

    user = User(
        email=email,
        password_hash=hash_password(password),
    )

    try:
        db.add(user)
        db.commit()
        db.refresh(user)
    except IntegrityError as exc:
        db.rollback()
        sqlstate = getattr(exc.orig, "sqlstate", None)
        if sqlstate == _UNIQUE_VIOLATION:
            raise UserAlreadyExists() from exc
        raise
    except Exception:
        db.rollback()
        raise

    return user


def authenticate_user(
    db: Session,
    *,
    email: str,
    password: str,
) -> User:
    user = get_user_by_email(db, email)

    if user is None or not user.is_active:
        raise InvalidCredentials()

    if not verify_password(password, user.password_hash):
        raise InvalidCredentials()

    if password_needs_rehash(user.password_hash):
        new_hash = hash_password(password)
        try:
            user.password_hash = new_hash
            db.commit()
        except Exception:
            db.rollback()
            logger.warning("password_hash_upgrade_failed")

    settings = get_settings()
    if settings.auth_require_verified_email and user.email_verified_at is None:
        raise EmailVerificationRequired()

    return user


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _issue_one_time_token(
    db: Session,
    *,
    user_id: uuid.UUID,
    purpose: str,
    ttl: timedelta,
) -> str:
    now = _utcnow()

    # Only the newest active credential for a purpose remains valid.
    active = db.execute(
        select(AuthOneTimeToken)
        .where(
            AuthOneTimeToken.user_id == user_id,
            AuthOneTimeToken.purpose == purpose,
            AuthOneTimeToken.consumed_at.is_(None),
            AuthOneTimeToken.expires_at > now,
        )
        .with_for_update()
    ).scalars()
    for row in active:
        row.consumed_at = now

    raw = secrets.token_urlsafe(48)
    db.add(
        AuthOneTimeToken(
            user_id=user_id,
            purpose=purpose,
            token_hash=_hash_token(raw),
            expires_at=now + ttl,
        )
    )
    return raw


def issue_email_verification_token(
    db: Session,
    *,
    user_id: uuid.UUID,
) -> str:
    settings = get_settings()
    return _issue_one_time_token(
        db,
        user_id=user_id,
        purpose=EMAIL_VERIFICATION_PURPOSE,
        ttl=timedelta(hours=settings.auth_email_verification_expire_hours),
    )


def issue_password_reset_token(
    db: Session,
    *,
    user_id: uuid.UUID,
) -> str:
    settings = get_settings()
    return _issue_one_time_token(
        db,
        user_id=user_id,
        purpose=PASSWORD_RESET_PURPOSE,
        ttl=timedelta(minutes=settings.auth_password_reset_expire_minutes),
    )


def _consume_one_time_token(
    db: Session,
    *,
    raw_token: str,
    purpose: str,
) -> AuthOneTimeToken:
    now = _utcnow()
    row = db.execute(
        select(AuthOneTimeToken)
        .where(
            AuthOneTimeToken.token_hash == _hash_token(raw_token),
            AuthOneTimeToken.purpose == purpose,
            AuthOneTimeToken.consumed_at.is_(None),
            AuthOneTimeToken.expires_at > now,
        )
        .with_for_update()
    ).scalar_one_or_none()
    if row is None:
        if purpose == PASSWORD_RESET_PURPOSE:
            raise PasswordResetInvalid()
        raise EmailVerificationInvalid()

    row.consumed_at = now
    return row


def verify_email(
    db: Session,
    *,
    token: str,
) -> User:
    row = _consume_one_time_token(
        db,
        raw_token=token,
        purpose=EMAIL_VERIFICATION_PURPOSE,
    )
    user = db.get(User, row.user_id)
    if user is None or not user.is_active:
        raise EmailVerificationInvalid()

    user.email_verified_at = _utcnow()
    return user


def reset_password(
    db: Session,
    *,
    token: str,
    new_password: str,
) -> User:
    row = _consume_one_time_token(
        db,
        raw_token=token,
        purpose=PASSWORD_RESET_PURPOSE,
    )
    user = db.get(User, row.user_id)
    if user is None or not user.is_active:
        raise PasswordResetInvalid()

    user.password_hash = hash_password(new_password)
    user.security_version += 1
    revoke_all_sessions(db, user_id=user.id)
    return user


def create_refresh_session(
    db: Session,
    *,
    user_id: uuid.UUID,
    ip_address: str | None,
    user_agent: str | None,
) -> tuple[AuthSession, str]:
    settings = get_settings()
    now = _utcnow()

    session = AuthSession(
        user_id=user_id,
        token_hash="pending",
        expires_at=now + timedelta(days=settings.auth_refresh_token_expire_days),
        ip_address=ip_address,
        user_agent=(user_agent or "")[:1000] or None,
    )
    db.add(session)
    db.flush()

    secret = secrets.token_urlsafe(48)
    raw_token = f"{session.id}.{secret}"
    session.token_hash = _hash_token(raw_token)

    _trim_active_sessions(db, user_id=user_id)
    return session, raw_token


def _parse_refresh_token(raw_token: str) -> tuple[uuid.UUID, str]:
    try:
        raw_id, secret = raw_token.split(".", 1)
        session_id = uuid.UUID(raw_id)
    except (ValueError, AttributeError):
        raise RefreshTokenInvalid()
    if not secret:
        raise RefreshTokenInvalid()
    return session_id, raw_token


def rotate_refresh_session(
    db: Session,
    *,
    refresh_token: str,
    ip_address: str | None,
    user_agent: str | None,
) -> tuple[User, AuthSession, str]:
    session_id, normalized_token = _parse_refresh_token(refresh_token)
    session = db.execute(
        select(AuthSession)
        .where(AuthSession.id == session_id)
        .with_for_update()
    ).scalar_one_or_none()

    now = _utcnow()
    if (
        session is None
        or session.revoked_at is not None
        or session.expires_at <= now
        or session.token_hash != _hash_token(normalized_token)
    ):
        raise RefreshTokenInvalid()

    user = db.get(User, session.user_id)
    if user is None or not user.is_active:
        raise RefreshTokenInvalid()

    new_raw = f"{session.id}.{secrets.token_urlsafe(48)}"
    session.token_hash = _hash_token(new_raw)
    session.last_used_at = now
    session.ip_address = ip_address
    session.user_agent = (user_agent or "")[:1000] or None
    return user, session, new_raw


def revoke_session(
    db: Session,
    *,
    refresh_token: str,
) -> bool:
    try:
        session_id, normalized_token = _parse_refresh_token(refresh_token)
    except RefreshTokenInvalid:
        return False

    session = db.execute(
        select(AuthSession)
        .where(
            AuthSession.id == session_id,
            AuthSession.revoked_at.is_(None),
            AuthSession.token_hash == _hash_token(normalized_token),
        )
        .with_for_update()
    ).scalar_one_or_none()
    if session is None:
        return False
    session.revoked_at = _utcnow()
    return True


def revoke_session_by_id(
    db: Session,
    *,
    user_id: uuid.UUID,
    session_id: uuid.UUID,
) -> bool:
    session = db.execute(
        select(AuthSession)
        .where(
            AuthSession.id == session_id,
            AuthSession.user_id == user_id,
            AuthSession.revoked_at.is_(None),
        )
        .with_for_update()
    ).scalar_one_or_none()
    if session is None:
        return False
    session.revoked_at = _utcnow()
    db.flush()
    return True


def revoke_all_sessions(
    db: Session,
    *,
    user_id: uuid.UUID,
) -> int:
    now = _utcnow()
    rows = list(
        db.execute(
            select(AuthSession).where(
                AuthSession.user_id == user_id,
                AuthSession.revoked_at.is_(None),
            )
        ).scalars()
    )
    for row in rows:
        row.revoked_at = now
    return len(rows)


def list_active_sessions(
    db: Session,
    *,
    user_id: uuid.UUID,
) -> list[AuthSession]:
    now = _utcnow()
    return list(
        db.execute(
            select(AuthSession)
            .where(
                AuthSession.user_id == user_id,
                AuthSession.revoked_at.is_(None),
                AuthSession.expires_at > now,
            )
            .order_by(AuthSession.created_at.desc())
        ).scalars()
    )


def _trim_active_sessions(
    db: Session,
    *,
    user_id: uuid.UUID,
) -> None:
    settings = get_settings()
    sessions = list_active_sessions(db, user_id=user_id)
    max_sessions = settings.auth_max_sessions
    for stale in sessions[max_sessions :]:
        stale.revoked_at = _utcnow()
