"""Unified provider-usage contract on top of M37 usage_events."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.services.usage import record_event


@dataclass(frozen=True)
class ProviderUsage:
    """Normalized provider call accounting payload."""

    capability: str
    operation: str
    provider: str
    model: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    units: int = 1
    request_id: str | None = None
    provider_request_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.units < 1:
            raise ValueError("provider usage units must be >= 1")
        if self.input_tokens < 0 or self.output_tokens < 0:
            raise ValueError("token counts must be >= 0")


def record_provider_usage(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID | None,
    source_id: uuid.UUID | None,
    usage: ProviderUsage,
    idempotency_key: str,
) -> Any:
    """Persist a provider call as workspace-scoped authoritative usage."""

    metadata = {
        "capability": usage.capability,
        "operation": usage.operation,
        "provider": usage.provider,
        "model": usage.model,
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
        **usage.metadata,
    }
    if usage.request_id:
        metadata["request_id"] = usage.request_id
    if usage.provider_request_id:
        metadata["provider_request_id"] = usage.provider_request_id

    return record_event(
        db,
        workspace_id=workspace_id,
        user_id=user_id,
        metric="ai_generation_units",
        quantity=usage.units,
        idempotency_key=idempotency_key,
        source_type="provider_call",
        source_id=source_id,
        metadata=metadata,
    )


__all__ = ["ProviderUsage", "record_provider_usage"]
