"""Password hashing and JWT primitives."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHash, VerifyMismatchError

from app.core.config import get_settings

_hasher = PasswordHasher(
    time_cost=2,
    memory_cost=19 * 1024,
    parallelism=1,
    hash_len=32,
    salt_len=16,
)


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    try:
        _hasher.verify(password_hash, plain_password)
    except (VerifyMismatchError, InvalidHash):
        return False
    return True


def password_needs_rehash(password_hash: str) -> bool:
    try:
        return _hasher.check_needs_rehash(password_hash)
    except (VerifyMismatchError, InvalidHash):
        return True


def create_access_token(subject: str, *, security_version: int = 1) -> str:
    settings = get_settings()

    now = datetime.now(UTC)
    expire = now + timedelta(
        minutes=settings.jwt_access_token_expire_minutes
    )

    payload: dict[str, Any] = {
        "sub": subject,
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "jti": str(uuid.uuid4()),
        "sv": int(security_version),
    }

    headers: dict[str, Any] = {
        "typ": settings.jwt_type,
    }

    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
        headers=headers,
    )


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and strictly validate a JWT."""
    settings = get_settings()

    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError as exc:
        raise jwt.InvalidTokenError("Invalid token header") from exc

    if header.get("typ") != settings.jwt_type:
        raise jwt.InvalidTokenError("Invalid token type")

    if header.get("alg") != settings.jwt_algorithm:
        raise jwt.InvalidTokenError("Invalid token algorithm")

    payload = jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
        issuer=settings.jwt_issuer,
        audience=settings.jwt_audience,
        leeway=settings.jwt_clock_skew_seconds,  # اضافه شد
        options={
            "require": ["exp", "iat", "sub", "iss", "aud"],
            "verify_signature": True,
            "verify_exp": True,
            "verify_iat": True,
            "verify_iss": True,
            "verify_aud": True,
        },
    )

    iat = payload.get("iat")
    now = datetime.now(UTC).timestamp()

    if (
        isinstance(iat, (int, float))
        and iat > now + settings.jwt_clock_skew_seconds
    ):
        raise jwt.InvalidTokenError("iat is in the future")

    return payload
