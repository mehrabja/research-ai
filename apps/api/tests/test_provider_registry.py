from __future__ import annotations

import pytest

from app.services.provider_registry import (
    ProviderDefinition,
    ProviderNotConfiguredError,
    ProviderRegistry,
)


def test_registry_preserves_configured_order(monkeypatch) -> None:
    monkeypatch.setenv("PROVIDER_GENERATION_CHAIN", "openai,backup")
    registry = ProviderRegistry()
    registry.register(
        ProviderDefinition("backup", "generation", lambda _: "backup")
    )
    registry.register(
        ProviderDefinition("openai", "generation", lambda _: "openai")
    )
    assert [d.name for d in registry.candidates("generation")] == [
        "openai",
        "backup",
    ]


def test_registry_rejects_missing_registered_provider(monkeypatch) -> None:
    monkeypatch.setenv("PROVIDER_GENERATION_CHAIN", "missing")
    registry = ProviderRegistry()
    with pytest.raises(ProviderNotConfiguredError):
        registry.candidates("generation")


def test_registry_resolves_requested_provider() -> None:
    registry = ProviderRegistry()
    registry.register(
        ProviderDefinition("one", "generation", lambda _: "one")
    )
    registry.register(
        ProviderDefinition("two", "generation", lambda _: "two")
    )
    assert registry.resolve("generation", requested="two") == "two"
