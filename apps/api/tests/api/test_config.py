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



def test_europepmc_source_settings_defaults() -> None:
    from app.core.config import Settings

    settings = Settings(database_url="postgresql://user:pass@localhost/test")
    assert settings.europepmc_base_url == (
        "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
    )
    assert settings.europepmc_timeout_seconds == 15.0
    assert settings.europepmc_max_retries == 2
    assert settings.europepmc_min_interval_seconds == 0.34
