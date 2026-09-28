import pytest


@pytest.fixture(autouse=True)
def _isolate_settings_env(monkeypatch):
    for key in (
        "DEBUG",
        "CORS_ALLOWED_ORIGINS",
        "CORS_ALLOWED_METHODS",
        "CORS_ALLOWED_HEADERS",
        "APP_ENV",
    ):
        monkeypatch.delenv(key, raising=False)