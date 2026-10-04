"""M39 provider-policy execution helpers.

This module owns the policy layer above concrete integrations:
- ordered preferred/fallback providers
- explicit capability matching
- retryable-provider failure handling
- auditable provider attempt metadata

It does not fabricate a provider or hide configuration failures.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from app.services.provider_registry import (
    ProviderCapability,
    ProviderDefinition,
    ProviderNotConfiguredError,
    get_provider_registry,
)

T = TypeVar("T")


class ProviderAttemptError(RuntimeError):
    """Raised when every eligible provider in a configured chain failed."""

    def __init__(
        self,
        capability: ProviderCapability,
        attempts: tuple[ProviderAttempt, ...],
    ) -> None:
        self.capability = capability
        self.attempts = attempts
        names = ", ".join(a.provider for a in attempts) or "none"
        super().__init__(
            f"all configured {capability} providers failed: {names}"
        )


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
    name = type(exc).__name__
    return name.endswith(
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
    """Execute against the ordered provider chain.

    Configuration errors are surfaced immediately. Runtime failures only
    advance to the next provider when they are explicitly retryable.
    """
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
            ProviderAttempt(provider=definition.name, success=True)
        )
        return ProviderExecution(
            value=value,
            provider=definition.name,
            attempts=tuple(attempts),
        )

    raise ProviderAttemptError(capability, tuple(attempts))


__all__ = [
    "ProviderAttempt",
    "ProviderAttemptError",
    "ProviderExecution",
    "execute_with_provider_fallback",
]
