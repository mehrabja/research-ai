"""M36 — fail-safe configuration tests."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def _base(**overrides) -> dict:
    base = {
        "_env_file": None,
        "debug": False,
        "cors_allowed_origins": "",
        "two_factor_encryption_key": "x" * 32,
        "database_url": (
            "postgresql+psycopg://t:t@localhost/t"
        ),
    }
    base.update(overrides)
    return base


def test_production_rejects_debug() -> None:
    with pytest.raises(ValidationError):
        Settings(
            **_base(
                app_env="production",
                jwt_secret_key="x" * 64,
                two_factor_encryption_key="x" * 32,
                auth_cookie_secure=True,
                auth_require_email_verification=True,
                email_provider="smtp",
                smtp_host="smtp.example.com",
                smtp_sender="no-reply@example.com",
                frontend_base_url="https://example.com",
                file_storage_backend="s3",
                file_storage_s3_bucket="test-bucket",
                file_storage_s3_region="us-east-1",
                file_storage_s3_access_key_id="test-key",
                file_storage_s3_secret_access_key="test-secret",
                debug=True,
            )
        )


def test_production_rejects_wildcard_cors() -> None:
    with pytest.raises(ValidationError):
        Settings(
            **_base(
                app_env="production",
                jwt_secret_key="x" * 64,
                two_factor_encryption_key="x" * 32,
                auth_cookie_secure=True,
                auth_require_email_verification=True,
                email_provider="smtp",
                smtp_host="smtp.example.com",
                smtp_sender="no-reply@example.com",
                frontend_base_url="https://example.com",
                file_storage_backend="s3",
                file_storage_s3_bucket="test-bucket",
                file_storage_s3_region="us-east-1",
                file_storage_s3_access_key_id="test-key",
                file_storage_s3_secret_access_key="test-secret",
                cors_allowed_origins="*",
            )
        )


def test_production_rejects_short_jwt() -> None:
    with pytest.raises(ValidationError):
        Settings(
            **_base(
                app_env="production",
                jwt_secret_key="short",
                two_factor_encryption_key="x" * 32,
                auth_cookie_secure=True,
                auth_require_email_verification=True,
                email_provider="smtp",
                smtp_host="smtp.example.com",
                smtp_sender="no-reply@example.com",
                frontend_base_url="https://example.com",
                file_storage_backend="s3",
                file_storage_s3_bucket="test-bucket",
                file_storage_s3_region="us-east-1",
                file_storage_s3_access_key_id="test-key",
                file_storage_s3_secret_access_key="test-secret",
            )
        )


def test_production_rejects_default_jwt() -> None:
    from app.core.config import DEV_JWT_SECRET

    with pytest.raises(ValidationError):
        Settings(
            **_base(
                app_env="production",
                jwt_secret_key=DEV_JWT_SECRET,
                two_factor_encryption_key="x" * 32,
                auth_cookie_secure=True,
                auth_require_email_verification=True,
                email_provider="smtp",
                smtp_host="smtp.example.com",
                smtp_sender="no-reply@example.com",
                frontend_base_url="https://example.com",
                file_storage_backend="s3",
                file_storage_s3_bucket="test-bucket",
                file_storage_s3_region="us-east-1",
                file_storage_s3_access_key_id="test-key",
                file_storage_s3_secret_access_key="test-secret",
            )
        )


def test_production_accepts_valid_config() -> None:
    s = Settings(
        **_base(
            app_env="production",
            jwt_secret_key="x" * 64,
            openrouter_api_key="test-openrouter-key",
            cors_allowed_origins="https://example.com",
            two_factor_encryption_key="x" * 32,
            auth_cookie_secure=True,
            auth_require_email_verification=True,
            email_provider="smtp",
            smtp_host="smtp.example.com",
            smtp_sender="no-reply@example.com",
            frontend_base_url="https://example.com",
            trusted_hosts="example.com",
            file_storage_backend="s3",
            file_storage_s3_bucket="test-bucket",
            file_storage_s3_region="us-east-1",
            file_storage_s3_access_key_id="test-key",
            file_storage_s3_secret_access_key="test-secret",
        )
    )
    assert s.app_env == "production"


def test_invalid_log_format_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(**_base(log_format="yaml"))


def test_invalid_rate_limit_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(**_base(rate_limit_global_per_minute=0))


def test_invalid_db_pool_size_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(**_base(db_pool_size=0))


def test_invalid_db_max_overflow_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(**_base(db_max_overflow=-1))


def test_backup_directory_must_not_be_empty() -> None:
    with pytest.raises(ValidationError):
        Settings(**_base(backup_directory="   "))
