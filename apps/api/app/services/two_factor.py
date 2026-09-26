"""Dependency-light TOTP with encrypted secret at rest."""
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
from app.db.models.auth import TwoFactorAuth

class TwoFactorError(AppError):
    code = "TWO_FACTOR_ERROR"
    status_code = 422
    message = "Two-factor operation failed."

def _fernet() -> Fernet:
    key = base64.urlsafe_b64encode(hashlib.sha256(get_settings().jwt_secret_key.encode()).digest())
    return Fernet(key)

def _secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")

def _hotp(secret: str, counter: int) -> str:
    key = base64.b32decode(secret + "=" * ((8 - len(secret) % 8) % 8), casefold=True)
    digest = hmac.new(key, counter.to_bytes(8, "big"), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = int.from_bytes(digest[offset:offset + 4], "big") & 0x7FFFFFFF
    return f"{value % 1_000_000:06d}"

def verify_code(secret: str, code: str, window: int = 1) -> bool:
    if len(code) != 6 or not code.isdigit():
        return False
    counter = int(time.time()) // 30
    return any(hmac.compare_digest(_hotp(secret, counter + delta), code) for delta in range(-window, window + 1))

def issuer() -> str:
    return get_settings().auth_totp_issuer

def begin_setup(db: Session, *, user_id: uuid.UUID, email: str) -> tuple[str, str]:
    secret = _secret()
    row = db.execute(select(TwoFactorAuth).where(TwoFactorAuth.user_id == user_id).with_for_update()).scalar_one_or_none()
    encrypted = _fernet().encrypt(secret.encode()).decode()
    if row is None:
        db.add(TwoFactorAuth(user_id=user_id, secret_ciphertext=encrypted, enabled=False, recovery_code_hashes=[]))
    else:
        row.secret_ciphertext = encrypted
        row.enabled = False
        row.recovery_code_hashes = []
    db.commit()
    label = f"{issuer()}:{email}"
    return secret, f"otpauth://totp/{label}?secret={secret}&issuer={issuer()}"

def _load(db: Session, user_id: uuid.UUID) -> TwoFactorAuth:
    row = db.execute(select(TwoFactorAuth).where(TwoFactorAuth.user_id == user_id).with_for_update()).scalar_one_or_none()
    if row is None:
        raise TwoFactorError()
    return row

def enable(db: Session, *, user_id: uuid.UUID, code: str) -> tuple[bool, list[str]]:
    row = _load(db, user_id)
    try:
        secret = _fernet().decrypt(row.secret_ciphertext.encode()).decode()
    except InvalidToken as exc:
        raise TwoFactorError("stored 2FA secret cannot be decrypted") from exc
    if not verify_code(secret, code):
        raise TwoFactorError("invalid verification code")
    recovery = [secrets.token_urlsafe(9) for _ in range(8)]
    row.enabled = True
    row.recovery_code_hashes = [hashlib.sha256(x.encode()).hexdigest() for x in recovery]
    db.commit()
    return True, recovery

def status(db: Session, *, user_id: uuid.UUID) -> tuple[bool, int]:
    row = db.execute(select(TwoFactorAuth).where(TwoFactorAuth.user_id == user_id)).scalar_one_or_none()
    return bool(row and row.enabled), len(row.recovery_code_hashes or []) if row else 0

def disable(db: Session, *, user_id: uuid.UUID) -> None:
    row = db.execute(select(TwoFactorAuth).where(TwoFactorAuth.user_id == user_id).with_for_update()).scalar_one_or_none()
    if row is not None:
        row.enabled = False
        row.recovery_code_hashes = []
        db.commit()
