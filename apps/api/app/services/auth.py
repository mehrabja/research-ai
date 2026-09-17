"""Authentication service."""
from __future__ import annotations

import logging

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import InvalidCredentials, UserAlreadyExists
from app.core.security import (
    hash_password,
    password_needs_rehash,
    verify_password,
)
from app.db.models.user import User

logger = logging.getLogger(__name__)

_UNIQUE_VIOLATION = "23505"


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

    if user is None:
        raise InvalidCredentials()

    if not user.is_active:
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

    return user
