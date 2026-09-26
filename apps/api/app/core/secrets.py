"""Provider-neutral secret resolution (M36).

Only an environment-backed resolver is provided. Real secret backends
(Vault, cloud secret managers, container secret injection) belong to a
later milestone and must plug in through ``SecretResolver``.

Rules:
  * secret values are never logged
  * secret values are never placed in API responses
  * secret values are never included in Settings repr/dumps
  * tests can swap the resolver and must restore it afterwards
"""
from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Protocol, runtime_checkable


@runtime_checkable
class SecretResolver(Protocol):
    def get_secret(self, key: str) -> str | None: ...


class EnvSecretResolver:
    """Resolve secrets from a mapping (defaults to ``os.environ``).

    Returns ``None`` for unset or empty values so callers can decide
    whether the secret is required.
    """

    def __init__(
        self, *, env: Mapping[str, str] | None = None
    ) -> None:
        self._env: Mapping[str, str] = (
            env if env is not None else os.environ
        )

    def get_secret(self, key: str) -> str | None:
        if not key:
            return None
        value = self._env.get(key)
        if value is None or value == "":
            return None
        return value


_default_resolver: SecretResolver = EnvSecretResolver()


def get_secret_resolver() -> SecretResolver:
    return _default_resolver


def set_secret_resolver(resolver: SecretResolver | None) -> None:
    global _default_resolver
    _default_resolver = (
        resolver if resolver is not None else EnvSecretResolver()
    )


__all__ = [
    "EnvSecretResolver",
    "SecretResolver",
    "get_secret_resolver",
    "set_secret_resolver",
]
