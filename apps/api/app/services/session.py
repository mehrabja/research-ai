"""Session creation, rotation and revocation for M39 auth."""
from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import AuthenticationRequired
from app.db.models.session import UserSession

REFRESH_COOKIE_NAME = "research_ai_refresh"
CSRF_COOKIE_NAME = "research_ai_csrf"


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _new_token() -> str:
    return secrets.token_urlsafe(48)


def create_session(
    db: Session,
    *,
    user_id: uuid.UUID,
    user_agent: str | None,
    ip_address: str | None,
) -> tuple[UserSession, str]:
    settings = get_settings()
    raw = _new_token()
    now = datetime.now(UTC)
    session = UserSession(
        user_id=user_id,
        refresh_token_hash=_hash_token(raw),
        expires_at=now + timedelta(days=settings.refresh_token_expire_days),
        last_used_at=now,
        user_agent=(user_agent or "")[:1000] or None,
        ip_address=(ip_address or "")[:255] or None,
    )
    db.add(session)
    db.flush()
    return session, raw


def rotate_session(
    db: Session,
    *,
    raw_refresh_token: str,
) -> tuple[UserSession, str]:
    if not raw_refresh_token:
        raise AuthenticationRequired()
    session = db.execute(
        select(UserSession).where(
            UserSession.refresh_token_hash == _hash_token(raw_refresh_token),
            UserSession.revoked_at.is_(None),
        )
        .with_for_update()
    ).scalar_one_or_none()
    if session is None:
        raise AuthenticationRequired()

    now = datetime.now(UTC)
    if session.expires_at <= now:
        session.revoked_at = now
        db.commit()
        raise AuthenticationRequired()

    new_raw = _new_token()
    session.refresh_token_hash = _hash_token(new_raw)
    session.last_used_at = now
    db.flush()
    return session, new_raw


def revoke_session(
    db: Session,
    *,
    user_id: uuid.UUID,
    session_id: uuid.UUID,
) -> None:
    session = db.execute(
        select(UserSession)
        .where(
            UserSession.id == session_id,
            UserSession.user_id == user_id,
            UserSession.revoked_at.is_(None),
        )
        .with_for_update()
    ).scalar_one_or_none()
    if session is not None:
        session.revoked_at = datetime.now(UTC)


def revoke_all_other_sessions(
    db: Session,
    *,
    user_id: uuid.UUID,
    except_session_id: uuid.UUID | None = None,
) -> int:
    rows = db.execute(
        select(UserSession)
        .where(
            UserSession.user_id == user_id,
            UserSession.revoked_at.is_(None),
        )
        .with_for_update()
    ).scalars().all()
    now = datetime.now(UTC)
    count = 0
    for session in rows:
        if except_session_id is not None and session.id == except_session_id:
            continue
        session.revoked_at = now
        count += 1
    return count


def list_active_sessions(db: Session, *, user_id: uuid.UUID) -> list[UserSession]:
    now = datetime.now(UTC)
    return list(
        db.execute(
            select(UserSession)
            .where(
                UserSession.user_id == user_id,
                UserSession.revoked_at.is_(None),
                UserSession.expires_at > now,
            )
            .order_by(UserSession.last_used_at.desc().nullslast())
        ).scalars().all()
    )


def revoke_by_refresh_token(
    db: Session,
    *,
    raw_refresh_token: str,
) -> bool:
    if not raw_refresh_token:
        return False
    session = db.execute(
        select(UserSession)
        .where(
            UserSession.refresh_token_hash == _hash_token(raw_refresh_token),
            UserSession.revoked_at.is_(None),
        )
        .with_for_update()
    ).scalar_one_or_none()
    if session is None:
        return False
    session.revoked_at = datetime.now(UTC)
    return True
