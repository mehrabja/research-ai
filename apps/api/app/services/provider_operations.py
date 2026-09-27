"""Helpers for auditable provider-operation lifecycle."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from time import monotonic
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.provider_operation import ProviderOperation


def start_operation(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    operation: str,
    capability: str,
    provider: str,
    model: str | None,
    project_id: uuid.UUID | None = None,
    report_id: uuid.UUID | None = None,
    job_id: uuid.UUID | None = None,
    request_id: str | None = None,
    idempotency_key: str | None = None,
    operation_metadata: dict[str, Any] | None = None,
) -> ProviderOperation:
    if idempotency_key is not None:
        existing = db.execute(
            select(ProviderOperation).where(
                ProviderOperation.workspace_id == workspace_id,
                ProviderOperation.idempotency_key == idempotency_key,
            )
        ).scalar_one_or_none()
        if existing is not None:
            return existing

    row = ProviderOperation(
        workspace_id=workspace_id,
        project_id=project_id,
        report_id=report_id,
        job_id=job_id,
        request_id=request_id,
        operation=operation,
        capability=capability,
        provider=provider,
        model=model,
        status="started",
        idempotency_key=idempotency_key,
        operation_metadata=operation_metadata,
    )
    db.add(row)
    db.flush()
    return row


def finish_operation(
    db: Session,
    *,
    operation_id: uuid.UUID,
    status: str,
    started_monotonic: float | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    total_tokens: int | None = None,
    cost_raw_usd: Any = None,
    cost_billable_usd: Any = None,
    error_code: str | None = None,
) -> ProviderOperation:
    row = db.get(ProviderOperation, operation_id)
    if row is None:
        raise LookupError(f"provider operation not found: {operation_id}")
    if row.status in {"succeeded", "failed", "canceled"}:
        return row
    if status not in {"succeeded", "failed", "canceled"}:
        raise ValueError(f"invalid provider operation terminal status: {status}")

    row.status = status
    row.input_tokens = input_tokens
    row.output_tokens = output_tokens
    row.total_tokens = total_tokens
    row.cost_raw_usd = cost_raw_usd
    row.cost_billable_usd = cost_billable_usd
    row.error_code = error_code
    if started_monotonic is not None:
        row.duration_ms = max(0, int((monotonic() - started_monotonic) * 1000))
    row.completed_at = datetime.now(UTC)
    db.flush()
    return row
