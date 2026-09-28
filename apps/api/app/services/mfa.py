from __future__ import annotations

import base64
import hashlib
import secrets
from datetime import UTC, datetime
import pyotp
from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings


_RECOVERY_COUNT = 8




def _cipher() -> Fernet:
    secret = get_settings().jwt_secret_key.encode("utf-8")
    key = base64.urlsafe_b64encode(hashlib.sha256(secret).digest())
    return Fernet(key)


def encrypt_secret(secret: str) -> str:
    return _cipher().encrypt(secret.encode("utf-8")).decode("ascii")


def decrypt_secret(value: str) -> str | None:
    try:
        return _cipher().decrypt(value.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError, UnicodeError):
        return None

def generate_secret() -> str:
    return pyotp.random_base32()


def provisioning_uri(secret: str, email: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(
        name=email,
        issuer_name=get_settings().auth_mfa_issuer,
    )


def verify_code(secret: str, code: str) -> bool:
    normalized = "".join(ch for ch in code if ch.isdigit())
    return len(normalized) == 6 and pyotp.TOTP(secret).verify(
        normalized,
        valid_window=1,
    )


def generate_recovery_codes() -> list[str]:
    return [secrets.token_hex(5) for _ in range(_RECOVERY_COUNT)]


def hash_recovery_code(code: str) -> str:
    import hashlib
    return hashlib.sha256(code.strip().lower().encode("utf-8")).hexdigest()


def hash_recovery_codes(codes: list[str]) -> list[str]:
    return [hash_recovery_code(code) for code in codes]


def consume_recovery_code(
    hashes: list[str],
    supplied: str,
) -> tuple[bool, list[str]]:
    digest = hash_recovery_code(supplied)
    if digest not in hashes:
        return False, hashes
    remaining = list(hashes)
    remaining.remove(digest)
    return True, remaining


def utcnow() -> datetime:
    return datetime.now(UTC)
