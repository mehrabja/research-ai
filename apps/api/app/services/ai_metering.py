"""Shared metering helper for AI operations."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.services.ai_operations import finish_operation, start_operation
from app.services.usage import record_event


def start_ai_meter(
    db: Session,
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
    db: Session,
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
    if success:
        # Product-unit charging remains policy-driven; one successful
        # operation is one product generation unit until plan policy
        # supplies a weighted formula.
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
