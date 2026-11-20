"""M36 — development-mode safety tests.

Development must not require paid services and must have safe defaults.
"""
from __future__ import annotations

from app.core.config import (
    DEV_JWT_SECRET,
    Settings,
)


def _dev(**overrides) -> Settings:
    base = {
        "_env_file": None,
        "debug": False,
        "cors_allowed_origins": "",
        "database_url": (
            "postgresql+psycopg://t:t@localhost/t"
        ),
    }
    base.update(overrides)
    return Settings(**base)


def test_dev_accepts_default_jwt(monkeypatch) -> None:
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
    s = _dev()
    assert s.jwt_secret_key == DEV_JWT_SECRET


def test_dev_default_debug_is_false() -> None:
    s = _dev()
    assert s.debug is False


def test_dev_default_log_format_is_text() -> None:
    s = _dev()
    assert s.log_format == "text"


def test_dev_cors_default_is_empty() -> None:
    s = _dev()
    assert s.cors_origins_list == []


def test_dev_secret_backend_env() -> None:
    s = _dev()
    assert s.secret_backend == "env"


def test_dev_rate_limit_enabled_by_default() -> None:
    s = _dev()
    assert s.rate_limit_enabled is True


def test_dev_no_paid_api_required() -> None:
    s = _dev()
    # All provider credentials default to empty strings.
    assert s.embedding_openai_api_key == ""
    assert s.generation_openai_api_key == ""
    assert s.semantic_scholar_api_key == ""


def test_dev_file_storage_local() -> None:
    s = _dev()
    assert s.file_storage_backend == "local"


def test_provider_defaults_use_openrouter() -> None:
    s = _dev()
    assert s.provider_generation_chain == "openrouter"
    assert s.provider_embedding_chain == "openrouter"
    assert s.provider_translation_chain == "openrouter"
    assert s.generation_provider == "openrouter"
    assert s.embedding_provider == "openrouter"
    assert s.translation_provider == "openrouter"
    assert s.openrouter_base_url == "https://openrouter.ai/api/v1"
