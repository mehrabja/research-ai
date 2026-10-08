"""M36 — Settings tests."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def _base(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
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


def test_defaults_safe() -> None:
    s = Settings(**_base())
    assert s.log_format == "text"
    assert s.cors_origins_list == []
    assert s.trusted_hosts_list == ["*"]
    assert s.rate_limit_enabled is True


def test_cors_csv_parsing() -> None:
    s = Settings(
        **_base(
            cors_allowed_origins=(
                "https://a.example, https://b.example"
            )
        )
    )
    assert s.cors_origins_list == [
        "https://a.example",
        "https://b.example",
    ]


def test_trusted_hosts_parsing() -> None:
    s = Settings(
        **_base(
            trusted_hosts="api.example.com,admin.example.com"
        )
    )
    assert s.trusted_hosts_list == [
        "api.example.com",
        "admin.example.com",
    ]


def test_production_rejects_wildcard_cors() -> None:
    with pytest.raises(ValidationError):
        Settings(
            **_base(
                app_env="production",
                jwt_secret_key="x" * 64,
                cors_allowed_origins="*",
            )
        )


def test_production_rejects_debug() -> None:
    with pytest.raises(ValidationError):
        Settings(
            **_base(
                app_env="production",
                jwt_secret_key="x" * 64,
                debug=True,
            )
        )


def test_rejects_invalid_log_format() -> None:
    with pytest.raises(ValidationError):
        Settings(**_base(log_format="yaml"))


def test_rejects_invalid_rate_limit() -> None:
    with pytest.raises(ValidationError):
        Settings(**_base(rate_limit_global_per_minute=0))


def test_settings_repr_hides_secrets() -> None:
    s = Settings(**_base())
    r = repr(s)
    assert "database_url" not in r
    assert s.database_url not in r
    assert "jwt_secret_key" not in r
    assert s.jwt_secret_key not in r
