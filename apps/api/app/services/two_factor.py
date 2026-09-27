"""TOTP and recovery-code service with encrypted-at-rest secrets."""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import struct
import uuid
from datetime import UTC, datetime

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import (
    AuthenticationRequired,
    TwoFactorInvalid,
    TwoFactorNotEnabled,
)
from app.db.models.security import UserTwoFactor

_ISSUER = "Research AI"
_STEP_SECONDS = 30
_DIGITS = 6
_WINDOW = 1


def _key() -> bytes:
    settings = get_settings()
    configured = settings.two_factor_encryption_key.strip()
    material = configured or settings.jwt_secret_key
    return hashlib.sha256(material.encode("utf-8")).digest()


def _encrypt(secret: str) -> str:
    nonce = secrets.token_bytes(12)
    ciphertext = AESGCM(_key()).encrypt(nonce, secret.encode("utf-8"), None)
    return base64.urlsafe_b64encode(nonce + ciphertext).decode("ascii")


def _decrypt(value: str) -> str:
    raw = base64.urlsafe_b64decode(value.encode("ascii"))
    nonce, ciphertext = raw[:12], raw[12:]
    return AESGCM(_key()).decrypt(nonce, ciphertext, None).decode("utf-8")


def _totp(secret: str, counter: int) -> str:
    key = base64.b32decode(secret.upper() + "=" * ((8 - len(secret) % 8) % 8))
    message = struct.pack(">Q", counter)
    digest = hmac.new(key, message, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = (
        ((digest[offset] & 0x7F) << 24)
        | (digest[offset + 1] << 16)
        | (digest[offset + 2] << 8)
        | digest[offset + 3]
    )
    return str(value % (10**_DIGITS)).zfill(_DIGITS)


def _step(now: datetime | None = None) -> int:
    current = now or datetime.now(UTC)
    return int(current.timestamp() // _STEP_SECONDS)


def verify_totp(
    secret: str,
    code: str,
    *,
    now: datetime | None = None,
    window: int = _WINDOW,
) -> int | None:
    current = _step(now)
    if len(code) != _DIGITS or not code.isdigit():
        return None
    for delta in range(-window, window + 1):
        candidate = current + delta
        if hmac.compare_digest(_totp(secret, candidate), code):
            return candidate
    return None


def _recovery_hash(code: str) -> str:
    return hashlib.sha256(code.strip().encode("utf-8")).hexdigest()


def _new_recovery_codes(count: int = 10) -> tuple[list[str], list[str]]:
    raw_codes = [
        f"{secrets.token_hex(4).upper()}-{secrets.token_hex(4).upper()}"
        for _ in range(count)
    ]
    return raw_codes, [_recovery_hash(code) for code in raw_codes]


def begin_enrollment(
    db: Session,
    *,
    user_id: uuid.UUID,
    email: str,
) -> tuple[UserTwoFactor, str, str, list[str]]:
    row = db.execute(
        select(UserTwoFactor)
        .where(UserTwoFactor.user_id == user_id)
        .with_for_update()
    ).scalar_one_or_none()

    secret = base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")
    raw_recovery, hashed_recovery = _new_recovery_codes()

    if row is None:
        row = UserTwoFactor(
            user_id=user_id,
            secret_encrypted=_encrypt(secret),
            recovery_codes=hashed_recovery,
            enabled_at=None,
            last_used_step=None,
        )
        db.add(row)
    else:
        if row.enabled_at is not None:
            raise TwoFactorInvalid("2FA is already enabled")
        row.secret_encrypted = _encrypt(secret)
        row.recovery_codes = hashed_recovery
        row.last_used_step = None

    db.flush()
    label = f"{_ISSUER}:{email}"
    uri = (
        "otpauth://totp/"
        + label.replace(" ", "%20")
        + f"?secret={secret}&issuer={_ISSUER.replace(' ', '%20')}"
        + f"&algorithm=SHA1&digits={_DIGITS}&period={_STEP_SECONDS}"
    )
    return row, secret, uri, raw_recovery


def confirm_enrollment(
    db: Session,
    *,
    user_id: uuid.UUID,
    code: str,
) -> UserTwoFactor:
    row = db.execute(
        select(UserTwoFactor)
        .where(UserTwoFactor.user_id == user_id)
        .with_for_update()
    ).scalar_one_or_none()
    if row is None:
        raise TwoFactorInvalid("2FA enrollment was not started")
    secret = _decrypt(row.secret_encrypted)
    step = verify_totp(secret, code)
    if step is None:
        raise TwoFactorInvalid()
    row.enabled_at = datetime.now(UTC)
    row.last_used_step = None
    db.commit()
    return row


def disable(
    db: Session,
    *,
    user_id: uuid.UUID,
    code: str,
) -> None:
    row = db.execute(
        select(UserTwoFactor)
        .where(UserTwoFactor.user_id == user_id)
        .with_for_update()
    ).scalar_one_or_none()
    if row is None or row.enabled_at is None:
        raise TwoFactorNotEnabled()

    secret = _decrypt(row.secret_encrypted)
    step = verify_totp(secret, code)
    if step is None:
        raise TwoFactorInvalid()
    row.enabled_at = None
    row.last_used_step = None
    db.commit()


def verify_second_factor(
    db: Session,
    *,
    user_id: uuid.UUID,
    code: str | None = None,
    recovery_code: str | None = None,
) -> bool:
    row = db.execute(
        select(UserTwoFactor)
        .where(UserTwoFactor.user_id == user_id)
        .with_for_update()
    ).scalar_one_or_none()
    if row is None or row.enabled_at is None:
        return True

    if recovery_code:
        candidate = _recovery_hash(recovery_code)
        for stored in list(row.recovery_codes or []):
            if hmac.compare_digest(candidate, stored):
                row.recovery_codes = [x for x in row.recovery_codes if x != stored]
                db.commit()
                return True
        raise AuthenticationRequired("invalid recovery code")

    if not code:
        raise AuthenticationRequired("two-factor authentication required")

    secret = _decrypt(row.secret_encrypted)
    step = verify_totp(secret, code)
    if step is None or (
        row.last_used_step is not None and step <= row.last_used_step
    ):
        raise AuthenticationRequired("invalid or replayed two-factor code")
    row.last_used_step = step
    db.flush()
    return True
