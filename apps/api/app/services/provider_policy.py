"""M39 ordered provider execution and fallback policy."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from app.services.provider_registry import (
    ProviderCapability,
    ProviderDefinition,
    get_provider_registry,
)

T = TypeVar("T")


class ProviderAttemptError(RuntimeError):
    """All configured eligible providers failed."""


@dataclass(frozen=True)
class ProviderAttempt:
    provider: str
    success: bool
    error_type: str | None = None


@dataclass(frozen=True)
class ProviderExecution(Generic[T]):
    value: T
    provider: str
    attempts: tuple[ProviderAttempt, ...]


def _default_retryable(exc: BaseException) -> bool:
    return type(exc).__name__.endswith(
        (
            "RateLimitError",
            "ProviderUnavailableError",
            "TimeoutError",
        )
    )


def execute_with_provider_fallback(
    capability: ProviderCapability,
    *,
    operation: Callable[[Any], T],
    requested_provider: str | None = None,
    config: Any = None,
    retryable: Callable[[BaseException], bool] = _default_retryable,
) -> ProviderExecution[T]:
    registry = get_provider_registry()
    definitions: tuple[ProviderDefinition, ...] = registry.candidates(
        capability,
        requested=requested_provider,
    )
    attempts: list[ProviderAttempt] = []

    for definition in definitions:
        provider = definition.factory(config)
        try:
            value = operation(provider)
        except BaseException as exc:
            attempts.append(
                ProviderAttempt(
                    provider=definition.name,
                    success=False,
                    error_type=type(exc).__name__,
                )
            )
            if not retryable(exc):
                raise
            continue

        attempts.append(
            ProviderAttempt(
                provider=definition.name,
                success=True,
            )
        )
        return ProviderExecution(
            value=value,
            provider=definition.name,
            attempts=tuple(attempts),
        )

    names = ", ".join(attempt.provider for attempt in attempts) or "none"
    raise ProviderAttemptError(
        f"all configured {capability} providers failed: {names}"
    )


__all__ = [
    "ProviderAttempt",
    "ProviderAttemptError",
    "ProviderExecution",
    "execute_with_provider_fallback",
]
