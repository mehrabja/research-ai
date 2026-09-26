"""M36 — Secret resolver tests."""
from __future__ import annotations

from app.core.secrets import (
    EnvSecretResolver,
    get_secret_resolver,
    set_secret_resolver,
)


def test_env_resolver_returns_value() -> None:
    r = EnvSecretResolver(env={"FOO": "bar"})
    assert r.get_secret("FOO") == "bar"


def test_env_resolver_missing() -> None:
    r = EnvSecretResolver(env={})
    assert r.get_secret("FOO") is None


def test_env_resolver_empty_value_is_none() -> None:
    r = EnvSecretResolver(env={"FOO": ""})
    assert r.get_secret("FOO") is None


def test_env_resolver_empty_key() -> None:
    r = EnvSecretResolver(env={"FOO": "bar"})
    assert r.get_secret("") is None


def test_default_resolver_is_env() -> None:
    assert isinstance(get_secret_resolver(), EnvSecretResolver)


def test_set_resolver_none_restores_default() -> None:
    set_secret_resolver(None)
    try:
        assert isinstance(
            get_secret_resolver(), EnvSecretResolver
        )
    finally:
        set_secret_resolver(None)


def test_resolver_replacement_is_isolated() -> None:
    class _Fake:
        def get_secret(self, key: str) -> str | None:
            return f"fake:{key}"

    original = get_secret_resolver()
    try:
        set_secret_resolver(_Fake())
        assert get_secret_resolver().get_secret("X") == "fake:X"
    finally:
        set_secret_resolver(original)
    assert isinstance(get_secret_resolver(), EnvSecretResolver) or (
        get_secret_resolver() is original
    )
