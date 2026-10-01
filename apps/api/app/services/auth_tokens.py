"""Email verification and password reset token lifecycle."""
from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import EmailVerificationInvalid, PasswordResetInvalid
from app.core.security import hash_password
from app.db.models.auth_tokens import (
    EmailVerificationToken,
    PasswordResetToken,
)
from app.db.models.user import User
from app.services.session import revoke_all_other_sessions


def _hash(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def _token() -> str:
    return secrets.token_urlsafe(48)


def issue_email_verification_token(
    db: Session,
    *,
    user_id: uuid.UUID,
) -> str:
    settings = get_settings()
    raw = _token()
    now = datetime.now(UTC)
    db.execute(
        update(EmailVerificationToken)
        .where(
            EmailVerificationToken.user_id == user_id,
            EmailVerificationToken.used_at.is_(None),
        )
        .values(used_at=now)
    )
    db.add(
        EmailVerificationToken(
            user_id=user_id,
            token_hash=_hash(raw),
            expires_at=now + timedelta(
                minutes=settings.email_verification_expire_minutes
            ),
        )
    )
    db.flush()
    return raw


def verify_email(
    db: Session,
    *,
    raw_token: str,
) -> User:
    row = db.execute(
        select(EmailVerificationToken)
        .where(
            EmailVerificationToken.token_hash == _hash(raw_token),
            EmailVerificationToken.used_at.is_(None),
        )
        .with_for_update()
    ).scalar_one_or_none()
    now = datetime.now(UTC)
    if row is None or row.expires_at <= now:
        raise EmailVerificationInvalid()
    user = db.get(User, row.user_id)
    if user is None or not user.is_active:
        raise EmailVerificationInvalid()
    row.used_at = now
    user.email_verified_at = now
    db.commit()
    return user


def issue_password_reset_token(
    db: Session,
    *,
    user_id: uuid.UUID,
) -> str:
    settings = get_settings()
    raw = _token()
    now = datetime.now(UTC)
    db.execute(
        update(PasswordResetToken)
        .where(
            PasswordResetToken.user_id == user_id,
            PasswordResetToken.used_at.is_(None),
        )
        .values(used_at=now)
    )
    db.add(
        PasswordResetToken(
            user_id=user_id,
            token_hash=_hash(raw),
            expires_at=now + timedelta(
                minutes=settings.password_reset_expire_minutes
            ),
        )
    )
    db.flush()
    return raw


def reset_password(
    db: Session,
    *,
    raw_token: str,
    new_password: str,
) -> User:
    row = db.execute(
        select(PasswordResetToken)
        .where(
            PasswordResetToken.token_hash == _hash(raw_token),
            PasswordResetToken.used_at.is_(None),
        )
        .with_for_update()
    ).scalar_one_or_none()
    now = datetime.now(UTC)
    if row is None or row.expires_at <= now:
        raise PasswordResetInvalid()
    user = db.get(User, row.user_id)
    if user is None or not user.is_active:
        raise PasswordResetInvalid()
    row.used_at = now
    user.password_hash = hash_password(new_password)
    revoke_all_other_sessions(
        db,
        user_id=user.id,
        except_session_id=None,
    )
    db.commit()
    return user
