"""M36 — fail-safe configuration tests."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def _base(**overrides) -> dict:
    base = {
        "_env_file": None,
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
                debug=True,
            )
        )


def test_production_rejects_wildcard_cors() -> None:
    with pytest.raises(ValidationError):
        Settings(
            **_base(
                app_env="production",
                jwt_secret_key="x" * 64,
                cors_allowed_origins="*",
            )
        )


def test_production_rejects_short_jwt() -> None:
    with pytest.raises(ValidationError):
        Settings(
            **_base(
                app_env="production",
                jwt_secret_key="short",
            )
        )


def test_production_rejects_default_jwt() -> None:
    from app.core.config import DEV_JWT_SECRET

    with pytest.raises(ValidationError):
        Settings(
            **_base(
                app_env="production",
                jwt_secret_key=DEV_JWT_SECRET,
            )
        )


def test_production_accepts_valid_config() -> None:
    s = Settings(
        **_base(
            app_env="production",
            jwt_secret_key="x" * 64,
            cors_allowed_origins="https://example.com",
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
