"""Provider-call metering with durable audit records.

Provider calls are recorded in a short, independent DB transaction so a
business transaction rollback cannot erase evidence that the external
provider was actually called. Product/billable units remain a separate
policy decision and are not recorded by this helper.
"""
from __future__ import annotations

import uuid
import json
from collections.abc import Callable
from datetime import datetime
from time import monotonic
from typing import Any, TypeVar

from app.db.session import SessionLocal
from app.services.ai_operations import finish_operation, start_operation
from app.services.usage import record_event

T = TypeVar("T")


def _error_code(exc: BaseException) -> str:
    name = type(exc).__name__
    mapping = {
        "GenerationRateLimitError": "provider_rate_limited",
        "EmbeddingRateLimitError": "provider_rate_limited",
        "TranslationRateLimitError": "provider_rate_limited",
        "GenerationTimeoutError": "provider_timeout",
        "TranslationTimeoutError": "provider_timeout",
        "GenerationProviderUnavailableError": "provider_unavailable",
        "EmbeddingProviderUnavailableError": "provider_unavailable",
        "TranslationProviderUnavailableError": "provider_unavailable",
        "GenerationAuthenticationError": "provider_authentication",
        "EmbeddingAuthenticationError": "provider_authentication",
        "TranslationAuthenticationError": "provider_authentication",
    }
    return mapping.get(name, name.removesuffix("Error").lower() or "provider_error")


def _record_provider_usage(
    *,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID | None,
    operation: str,
    operation_id: uuid.UUID,
    source_id: uuid.UUID | None,
    input_units: int | None,
    output_units: int | None,
    occurred_at: datetime | None,
) -> None:
    with SessionLocal() as db:
        if input_units is not None and input_units > 0:
            record_event(
                db,
                workspace_id=workspace_id,
                metric="ai_input_tokens",
                quantity=input_units,
                user_id=user_id,
                source_type="provider_call",
                source_id=source_id,
                usage_class="provider",
                idempotency_key=f"{operation}:input:{operation_id}",
                occurred_at=occurred_at,
            )
        if output_units is not None and output_units > 0:
            record_event(
                db,
                workspace_id=workspace_id,
                metric="ai_output_tokens",
                quantity=output_units,
                user_id=user_id,
                source_type="provider_call",
                source_id=source_id,
                usage_class="provider",
                idempotency_key=f"{operation}:output:{operation_id}",
                occurred_at=occurred_at,
            )
        db.commit()


def execute_metered_provider_call(
    call: Callable[[], T],
    *,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID | None,
    operation: str,
    capability: str,
    provider: Any,
    model: str | None = None,
    project_id: uuid.UUID | None = None,
    report_id: uuid.UUID | None = None,
    job_id: uuid.UUID | None = None,
    request_id: str | None = None,
    input_units: Callable[[T], int | None] | None = None,
    output_units: Callable[[T], int | None] | None = None,
    metadata: dict[str, Any] | None = None,
) -> T:
    """Execute an external provider call and persist success/failure.

    The operation row is opened and committed before the network call.
    Terminal state and provider usage are persisted afterwards in a
    separate transaction.
    """
    provider_name = (
        provider if isinstance(provider, str) else getattr(provider, "provider_name", None)
    )
    model_name = (
        model
        if model is not None
        else (
            provider if isinstance(provider, str)
            else getattr(provider, "model_name", None)
        )
    )

    with SessionLocal() as db:
        op = start_operation(
            db,
            workspace_id=workspace_id,
            user_id=user_id,
            operation=operation,
            provider=provider_name,
            model=model_name,
            project_id=project_id,
            report_id=report_id,
            job_id=job_id,
            request_id=request_id,
            metadata=metadata,
        )
        operation_id = op.id
        db.commit()

    started = monotonic()
    try:
        result = call()
    except BaseException as exc:
        with SessionLocal() as db:
            finish_operation(
                db,
                operation_id=operation_id,
                success=False,
                duration_ms=max(0, int((monotonic() - started) * 1000)),
                error_code=_error_code(exc),
                metadata={
                    **(metadata or {}),
                    "capability": capability,
                    "attempted_providers": list(
                        getattr(provider, "attempted_providers", [])
                    ),
                },
            )
            db.commit()
        raise

    in_units = input_units(result) if input_units is not None else None
    out_units = output_units(result) if output_units is not None else None

    with SessionLocal() as db:
        finish_operation(
            db,
            operation_id=operation_id,
            success=True,
            input_units=in_units,
            output_units=out_units,
            duration_ms=max(0, int((monotonic() - started) * 1000)),
            provider=getattr(result, "provider", None),
            model=getattr(result, "model", None),
            metadata={
                **(metadata or {}),
                "capability": capability,
                "attempted_providers": list(
                    getattr(provider, "attempted_providers", [])
                ),
            },
        )
        db.commit()

    _record_provider_usage(
        workspace_id=workspace_id,
        user_id=user_id,
        operation=operation,
        operation_id=operation_id,
        source_id=report_id,
        input_units=in_units,
        output_units=out_units,
        occurred_at=None,
    )
    return result


def start_ai_meter(
    db,
    *,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID | None,
    operation: str,
    provider: str | None,
    model: str | None,
    project_id: uuid.UUID | None = None,
    report_id: uuid.UUID | None = None,
    job_id: uuid.UUID | None = None,
    request_id: str | None = None,
    idempotency_key: str | None = None,
    metadata: dict[str, Any] | None = None,
):
    return start_operation(
        db,
        workspace_id=workspace_id,
        user_id=user_id,
        operation=operation,
        provider=provider,
        model=model,
        project_id=project_id,
        report_id=report_id,
        job_id=job_id,
        request_id=request_id,
        idempotency_key=idempotency_key,
        metadata=metadata,
    )


def finish_ai_meter(
    db,
    *,
    operation_id: uuid.UUID,
    success: bool,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID | None,
    operation: str,
    operation_source_id: uuid.UUID | None,
    input_units: int | None = None,
    output_units: int | None = None,
    duration_ms: int | None = None,
    estimated_cost_usd=None,
    error_code: str | None = None,
    occurred_at: datetime | None = None,
    record_internal: bool = True,
) -> None:
    finish_operation(
        db,
        operation_id=operation_id,
        success=success,
        input_units=input_units,
        output_units=output_units,
        duration_ms=duration_ms,
        estimated_cost_usd=estimated_cost_usd,
        error_code=error_code,
    )
    if input_units and input_units > 0:
        record_event(
            db,
            workspace_id=workspace_id,
            metric="ai_input_tokens",
            quantity=input_units,
            user_id=user_id,
            source_type="provider_call",
            source_id=operation_source_id,
            usage_class="provider",
            idempotency_key=f"{operation}:input:{operation_id}",
            occurred_at=occurred_at,
        )
    if output_units and output_units > 0:
        record_event(
            db,
            workspace_id=workspace_id,
            metric="ai_output_tokens",
            quantity=output_units,
            user_id=user_id,
            source_type="provider_call",
            source_id=operation_source_id,
            usage_class="provider",
            idempotency_key=f"{operation}:output:{operation_id}",
            occurred_at=occurred_at,
        )
    if success and record_internal:
        record_event(
            db,
            workspace_id=workspace_id,
            metric="ai_generation_units",
            quantity=1,
            user_id=user_id,
            source_type="provider_call",
            source_id=operation_source_id,
            usage_class="internal",
            idempotency_key=f"{operation}:internal:{operation_id}",
            occurred_at=occurred_at,
        )
