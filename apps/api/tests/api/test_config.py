"""Settings tests."""
from __future__ import annotations

from app.core.config import get_settings


def test_settings_load_database_url() -> None:
    settings = get_settings()
    assert settings.database_url
    assert settings.database_url.startswith("postgresql")


def test_settings_api_prefix_default() -> None:
    settings = get_settings()
    assert settings.api_prefix == "/api/v1"


def test_settings_database_url_not_in_repr() -> None:
    settings = get_settings()

    assert "database_url" not in repr(settings)
    assert settings.database_url not in repr(settings)
