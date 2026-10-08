"""Unit tests for password hashing, JWT primitives, and Settings guards."""
from __future__ import annotations

import base64
import json
import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from argon2 import PasswordHasher
from pydantic import ValidationError

from app.core.config import DEV_JWT_SECRET, Settings, get_settings
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    password_needs_rehash,
    verify_password,
)


# ===========================================================================
# Password hashing
# ===========================================================================
def test_hash_differs_from_plaintext() -> None:
    pwd = "correct horse battery staple!"
    h = hash_password(pwd)
    assert h != pwd
    assert pwd not in h
    assert h.startswith("$argon2id$")


def test_verify_correct() -> None:
    h = hash_password("correct horse battery staple!")
    assert verify_password("correct horse battery staple!", h) is True


def test_verify_wrong() -> None:
    h = hash_password("correct horse battery staple!")
    assert verify_password("wrong passphrase here", h) is False


def test_same_password_different_hashes() -> None:
    h1 = hash_password("same long password here")
    h2 = hash_password("same long password here")
    assert h1 != h2


def test_malformed_hash_returns_false() -> None:
    assert verify_password("any password", "not-a-valid-hash") is False


def test_long_password_accepted() -> None:
    pwd = "a" * 256
    h = hash_password(pwd)
    assert verify_password(pwd, h) is True


def test_unicode_password_accepted() -> None:
    pwd = "این یک گذرواژه طولانی است 🔐"
    h = hash_password(pwd)
    assert verify_password(pwd, h) is True


def test_password_with_spaces_accepted() -> None:
    pwd = "correct horse battery staple and more words"
    h = hash_password(pwd)
    assert verify_password(pwd, h) is True


def test_needs_rehash_false_for_current() -> None:
    assert password_needs_rehash(hash_password("a" * 20)) is False


def test_needs_rehash_true_for_old() -> None:
    weak = PasswordHasher(time_cost=1, memory_cost=8 * 1024, parallelism=1)
    assert password_needs_rehash(weak.hash("a" * 20)) is True


def test_needs_rehash_true_for_malformed() -> None:
    assert password_needs_rehash("not-a-valid-hash") is True


# ===========================================================================
# JWT creation
# ===========================================================================
def test_create_token_has_expected_claims() -> None:
    uid = uuid.uuid4()
    token = create_access_token(subject=str(uid))
    settings = get_settings()
    payload = jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
        audience=settings.jwt_audience,
        issuer=settings.jwt_issuer,
    )
    assert payload["sub"] == str(uid)
    assert payload["iss"] == settings.jwt_issuer
    assert payload["aud"] == settings.jwt_audience
    assert "exp" in payload
    assert "iat" in payload
    assert isinstance(payload["jti"], str) and payload["jti"]
    uuid.UUID(payload["jti"])  # must parse as UUID


def test_create_token_header_typ_and_alg() -> None:
    token = create_access_token(subject=str(uuid.uuid4()))
    header = jwt.get_unverified_header(token)
    settings = get_settings()
    assert header.get("typ") == settings.jwt_type
    assert header.get("alg") == settings.jwt_algorithm


def test_two_tokens_have_different_jti() -> None:
    uid = str(uuid.uuid4())
    t1 = create_access_token(subject=uid)
    t2 = create_access_token(subject=uid)
    j1 = decode_access_token(t1)["jti"]
    j2 = decode_access_token(t2)["jti"]
    assert j1 != j2


# ===========================================================================
# JWT decoding
# ===========================================================================
def _make_token(
    *,
    sub: object = "auto",
    iss: str | None = None,
    aud: str | None = None,
    iat: int | None = None,
    exp: int | None = None,
    typ: str | None = None,
    secret: str | None = None,
    alg: str | None = None,
) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload: dict[str, object] = {}
    if sub == "auto":
        payload["sub"] = str(uuid.uuid4())
    elif sub is not None:
        payload["sub"] = sub
    payload["iss"] = settings.jwt_issuer if iss is None else iss
    payload["aud"] = settings.jwt_audience if aud is None else aud
    payload["iat"] = int(now.timestamp()) if iat is None else iat
    payload["exp"] = (
        int((now + timedelta(minutes=5)).timestamp()) if exp is None else exp
    )
    payload["jti"] = str(uuid.uuid4())
    return jwt.encode(
        payload,
        settings.jwt_secret_key if secret is None else secret,
        algorithm=settings.jwt_algorithm if alg is None else alg,
        headers={"typ": settings.jwt_type if typ is None else typ},
    )


def test_decode_valid() -> None:
    uid = uuid.uuid4()
    token = create_access_token(subject=str(uid))
    assert decode_access_token(token)["sub"] == str(uid)


def test_decode_rejects_expired() -> None:
    past = datetime.now(UTC) - timedelta(minutes=5)
    token = _make_token(
        iat=int((past - timedelta(minutes=30)).timestamp()),
        exp=int(past.timestamp()),
    )
    with pytest.raises(jwt.PyJWTError):
        decode_access_token(token)


def test_decode_rejects_bad_signature() -> None:
    token = _make_token(secret="definitely-the-wrong-secret-but-long-enough-for-hs256-testing")
    with pytest.raises(jwt.PyJWTError):
        decode_access_token(token)


def test_decode_rejects_wrong_issuer() -> None:
    with pytest.raises(jwt.PyJWTError):
        decode_access_token(_make_token(iss="someone-else"))


def test_decode_rejects_wrong_audience() -> None:
    with pytest.raises(jwt.PyJWTError):
        decode_access_token(_make_token(aud="other-audience"))


def test_decode_rejects_wrong_typ() -> None:
    with pytest.raises(jwt.PyJWTError):
        decode_access_token(_make_token(typ="refresh+jwt"))


def test_decode_rejects_missing_sub() -> None:
    with pytest.raises(jwt.PyJWTError):
        decode_access_token(_make_token(sub=None))


def test_decode_rejects_missing_exp() -> None:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": str(uuid.uuid4()),
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "iat": int(now.timestamp()),
        "jti": str(uuid.uuid4()),
    }
    token = jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
        headers={"typ": settings.jwt_type},
    )
    with pytest.raises(jwt.PyJWTError):
        decode_access_token(token)


def test_decode_rejects_missing_iat() -> None:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": str(uuid.uuid4()),
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "exp": int((now + timedelta(minutes=5)).timestamp()),
        "jti": str(uuid.uuid4()),
    }
    token = jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
        headers={"typ": settings.jwt_type},
    )
    with pytest.raises(jwt.PyJWTError):
        decode_access_token(token)


def test_decode_accepts_iat_within_skew() -> None:
    now = datetime.now(UTC)
    # iat 10 seconds in the future, inside the default 30-second skew.
    future_iat = int((now + timedelta(seconds=10)).timestamp())
    token = _make_token(
        iat=future_iat,
        exp=int((now + timedelta(minutes=5)).timestamp()),
    )
    # Should not raise.
    decode_access_token(token)


def test_decode_rejects_future_iat_beyond_skew() -> None:
    settings = get_settings()
    now = datetime.now(UTC)
    far_future = int(
        (now + timedelta(seconds=settings.jwt_clock_skew_seconds + 60)).timestamp()
    )
    token = _make_token(
        iat=far_future,
        exp=int((now + timedelta(minutes=10)).timestamp()),
    )
    with pytest.raises(jwt.PyJWTError):
        decode_access_token(token)


def test_decode_rejects_alg_none() -> None:
    settings = get_settings()
    now = datetime.now(UTC)
    header = {"alg": "none", "typ": settings.jwt_type}
    payload = {
        "sub": str(uuid.uuid4()),
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=5)).timestamp()),
        "jti": str(uuid.uuid4()),
    }

    def b64(obj: dict) -> str:
        raw = json.dumps(obj, separators=(",", ":")).encode()
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")

    token = f"{b64(header)}.{b64(payload)}."
    with pytest.raises(jwt.PyJWTError):
        decode_access_token(token)


# ===========================================================================
# Settings — production secret guard
# ===========================================================================
def test_settings_repr_hides_secrets() -> None:
    settings = get_settings()
    r = repr(settings)
    assert "database_url" not in r
    assert settings.database_url not in r
    assert "jwt_secret_key" not in r
    assert settings.jwt_secret_key not in r


def test_production_rejects_default_secret() -> None:
    with pytest.raises(ValidationError):
        Settings(
            app_env="production",
            jwt_secret_key=DEV_JWT_SECRET,
            _env_file=None,
            database_url="postgresql+psycopg://test:test@localhost/test",
        )


def test_production_rejects_short_secret() -> None:
    with pytest.raises(ValidationError):
        Settings(
            app_env="production",
            jwt_secret_key="too-short",
            _env_file=None,
            database_url="postgresql+psycopg://test:test@localhost/test",
        )


def test_production_accepts_strong_secret() -> None:
    s = Settings(
        app_env="production",
        jwt_secret_key="x" * 64,
        two_factor_encryption_key="x" * 32,
        _env_file=None,
        database_url="postgresql+psycopg://test:test@localhost/test",
    )
    assert s.app_env == "production"


def test_development_accepts_default_secret() -> None:
    s = Settings(
        app_env="development",
        jwt_secret_key=DEV_JWT_SECRET,
        database_url="postgresql+psycopg://test:test@localhost/test",
    )
    assert s.jwt_secret_key == DEV_JWT_SECRET


def test_settings_rejects_non_hs256_algorithm() -> None:
    """jwt_algorithm is Literal['HS256'] — anything else must fail."""
    with pytest.raises(ValidationError):
        Settings(
            app_env="development",
            jwt_algorithm="RS256",  # type: ignore[arg-type]
            database_url="postgresql+psycopg://test:test@localhost/test",
        )

def test_evidence_source_query_is_report_scoped():
    from types import SimpleNamespace

    from app.services import evidence_matrix

    report_id = uuid.uuid4()
    source_id = uuid.uuid4()
    claim_id = uuid.uuid4()

    class Result:
        def __init__(self, value):
            self._value = value

        def scalar_one_or_none(self):
            return self._value

    class FakeDB:
        def __init__(self):
            self.calls = []

        def execute(self, statement):
            self.calls.append(statement)
            if len(self.calls) == 1:
                return Result(SimpleNamespace(id=report_id))
            if len(self.calls) == 2:
                return Result(SimpleNamespace(id=claim_id))
            return Result(None)

        def add(self, _row):
            raise AssertionError("foreign source must be rejected before insert")

    db = FakeDB()
    with pytest.raises(ValueError, match="does not belong to report"):
        evidence_matrix.add_evidence(
            db,
            report_id=report_id,
            user_id=uuid.uuid4(),
            claim_id=claim_id,
            evidence_type="source",
            evidence_id=source_id,
            source_id=source_id,
            support_level="supports",
            relevance_score=0.5,
            provenance={},
        )

    source_statement = db.calls[2]
    sql = str(source_statement.compile(compile_kwargs={"literal_binds": False}))
    assert "sources.report_id" in sql


def test_evidence_claim_rejects_foreign_manuscript_version() -> None:
    from types import SimpleNamespace

    from app.services import evidence_matrix

    report_id = uuid.uuid4()
    run_id = uuid.uuid4()
    foreign_version_id = uuid.uuid4()

    class Result:
        def __init__(self, value):
            self._value = value

        def scalar_one_or_none(self):
            return self._value

    class FakeDB:
        def __init__(self):
            self.calls = []
            self.added = False

        def execute(self, statement):
            self.calls.append(statement)
            if len(self.calls) == 1:
                return Result(SimpleNamespace(id=report_id))
            if len(self.calls) == 2:
                return Result(SimpleNamespace(id=run_id))
            return Result(None)

        def add(self, _row):
            self.added = True

    db = FakeDB()
    with pytest.raises(
        ValueError, match="manuscript version does not belong to report"
    ):
        evidence_matrix.create_claim(
            db,
            report_id=report_id,
            user_id=uuid.uuid4(),
            citation_run_id=run_id,
            manuscript_version_id=foreign_version_id,
            manuscript_section_id=None,
            claim_text="A scoped research claim.",
            claim_type="background",
            location=None,
        )

    assert db.added is False
    assert len(db.calls) == 3
