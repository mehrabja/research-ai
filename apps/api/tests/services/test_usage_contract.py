from __future__ import annotations

import uuid

import pytest

from app.services import usage_contract
from app.services.usage_contract import ProviderUsage


def test_provider_usage_rejects_invalid_quantities() -> None:
    with pytest.raises(ValueError):
        ProviderUsage(
            capability="generation",
            operation="generate",
            provider="openai",
            units=0,
        )

    with pytest.raises(ValueError):
        ProviderUsage(
            capability="generation",
            operation="generate",
            provider="openai",
            input_tokens=-1,
        )


def test_record_provider_usage_maps_provider_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_record_event(db: object, **kwargs: object) -> object:
        captured.update(kwargs)
        return "event"

    monkeypatch.setattr("app.services.usage.record_event", fake_record_event)

    source_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    usage = ProviderUsage(
        capability="generation",
        operation="generate",
        provider="openai",
        model="gpt-4o-mini",
        input_tokens=11,
        output_tokens=7,
        units=18,
        request_id="req-1",
        provider_request_id="openai-1",
        metadata={"temperature": 0.2},
    )

    result = usage_contract.record_provider_usage(
        object(),
        workspace_id=workspace_id,
        user_id=None,
        source_id=source_id,
        usage=usage,
        idempotency_key="provider-call:1",
    )

    assert result == "event"
    assert captured["workspace_id"] == workspace_id
    assert captured["metric"] == "ai_generation_units"
    assert captured["quantity"] == 18
    assert captured["idempotency_key"] == "provider-call:1"
    assert captured["source_type"] == "provider_call"
    assert captured["source_id"] == source_id
    metadata = captured["metadata"]
    assert isinstance(metadata, dict)
    assert metadata["capability"] == "generation"
    assert metadata["provider"] == "openai"
    assert metadata["input_tokens"] == 11
    assert metadata["output_tokens"] == 7
    assert metadata["request_id"] == "req-1"
    assert metadata["provider_request_id"] == "openai-1"
    assert metadata["temperature"] == 0.2


def test_record_provider_usage_preserves_metric_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_record_event(db: object, **kwargs: object) -> object:
        captured.update(kwargs)
        return "event"

    monkeypatch.setattr("app.services.usage.record_event", fake_record_event)

    usage = ProviderUsage(
        capability="source_discovery",
        operation="source_search",
        provider="openalex",
        metric="search_requests",
        units=1,
    )

    usage_contract.record_provider_usage(
        object(),
        workspace_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        source_id=None,
        usage=usage,
        idempotency_key="search-call:1",
    )

    assert captured["metric"] == "search_requests"
    assert captured["quantity"] == 1
