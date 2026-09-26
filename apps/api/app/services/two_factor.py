"""Minimal TOTP service with encrypted secrets."""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import time

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.db.models.auth_security import TwoFactorAuth


class TwoFactorError(AppError):
    code = "TWO_FACTOR_ERROR"
    status_code = 422
    message = "Two-factor operation failed."


def _fernet() -> Fernet:
    digest = hashlib.sha256(
        get_settings().jwt_secret_key.encode("utf-8")
    ).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def _new_secret() -> str:
    return base64.b32encode(
        secrets.token_bytes(20)
    ).decode("ascii").rstrip("=")


def decrypt_secret(ciphertext: str) -> str:
    try:
        return _fernet().decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise TwoFactorError(
            "Stored two-factor secret cannot be decrypted."
        ) from exc


def _hotp(secret: str, counter: int) -> str:
    padding = "=" * ((8 - len(secret) % 8) % 8)
    key = base64.b32decode(secret + padding, casefold=True)
    digest = hmac.new(
        key,
        counter.to_bytes(8, "big"),
        hashlib.sha1,
    ).digest()
    offset = digest[-1] & 0x0F
    value = int.from_bytes(
        digest[offset : offset + 4],
        "big",
    ) & 0x7FFFFFFF
    return f"{value % 1_000_000:06d}"


def verify_code(
    secret: str,
    code: str,
    *,
    window: int = 1,
) -> bool:
    if len(code) != 6 or not code.isdigit():
        return False

    counter = int(time.time()) // 30
    return any(
        hmac.compare_digest(
            _hotp(secret, counter + delta),
            code,
        )
        for delta in range(-window, window + 1)
    )


def issuer() -> str:
    return get_settings().auth_totp_issuer


def begin_setup(
    db: Session,
    *,
    user_id,
    email: str,
) -> tuple[str, str]:
    secret = _new_secret()
    encrypted = _fernet().encrypt(
        secret.encode("utf-8")
    ).decode("utf-8")

    row = db.execute(
        select(TwoFactorAuth)
        .where(TwoFactorAuth.user_id == user_id)
        .with_for_update()
    ).scalar_one_or_none()

    if row is None:
        db.add(
            TwoFactorAuth(
                user_id=user_id,
                secret_ciphertext=encrypted,
                enabled=False,
                recovery_code_hashes=[],
            )
        )
    else:
        row.secret_ciphertext = encrypted
        row.enabled = False
        row.recovery_code_hashes = []

    db.commit()

    label = f"{issuer()}:{email}"
    url = (
        "otpauth://totp/"
        f"{label}?secret={secret}&issuer={issuer()}"
    )
    return secret, url


def enable(
    db: Session,
    *,
    user_id,
    code: str,
) -> list[str]:
    row = db.execute(
        select(TwoFactorAuth)
        .where(TwoFactorAuth.user_id == user_id)
        .with_for_update()
    ).scalar_one_or_none()

    if row is None:
        raise TwoFactorError("Two-factor setup has not been started.")

    secret = decrypt_secret(row.secret_ciphertext)
    if not verify_code(secret, code):
        raise TwoFactorError("Invalid two-factor code.")

    recovery_codes = [
        secrets.token_urlsafe(9)
        for _ in range(8)
    ]
    row.enabled = True
    row.recovery_code_hashes = [
        hashlib.sha256(code.encode("utf-8")).hexdigest()
        for code in recovery_codes
    ]
    db.commit()
    return recovery_codes


def status(
    db: Session,
    *,
    user_id,
) -> tuple[bool, int]:
    row = db.execute(
        select(TwoFactorAuth).where(
            TwoFactorAuth.user_id == user_id
        )
    ).scalar_one_or_none()
    return (
        bool(row and row.enabled),
        len(row.recovery_code_hashes or []) if row else 0,
    )


def disable(
    db: Session,
    *,
    user_id,
) -> None:
    row = db.execute(
        select(TwoFactorAuth)
        .where(TwoFactorAuth.user_id == user_id)
        .with_for_update()
    ).scalar_one_or_none()
    if row is None:
        return

    row.enabled = False
    row.recovery_code_hashes = []
    db.commit()
