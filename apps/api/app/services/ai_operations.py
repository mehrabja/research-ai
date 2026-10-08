"""AI operation ledger service."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.ai_operation import AIOperation
from app.db.models.jobs import Job


def start_operation(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID | None,
    operation: str,
    provider: str | None = None,
    model: str | None = None,
    project_id: uuid.UUID | None = None,
    report_id: uuid.UUID | None = None,
    job_id: uuid.UUID | None = None,
    request_id: str | None = None,
    idempotency_key: str | None = None,
    metadata: dict | None = None,
) -> AIOperation:
    if job_id is not None and db.get(Job, job_id) is None:
        # Keep the audit row writable for direct service calls that carry
        # a correlation id without a persisted durable job.
        job_id = None

    if idempotency_key:
        existing = db.execute(
            select(AIOperation).where(
                AIOperation.workspace_id == workspace_id,
                AIOperation.operation == operation,
                AIOperation.idempotency_key == idempotency_key,
            )
        ).scalar_one_or_none()
        if existing is not None:
            return existing
    row = AIOperation(
        workspace_id=workspace_id,
        user_id=user_id,
        project_id=project_id,
        report_id=report_id,
        job_id=job_id,
        request_id=request_id,
        operation=operation,
        provider=provider,
        model=model,
        status="started",
        idempotency_key=idempotency_key,
        operation_metadata=metadata or {},
    )
    db.add(row)
    db.flush()
    return row


def finish_operation(
    db: Session,
    *,
    operation_id: uuid.UUID,
    success: bool,
    input_units: int | None = None,
    output_units: int | None = None,
    duration_ms: int | None = None,
    estimated_cost_usd: Decimal | None = None,
    error_code: str | None = None,
    provider: str | None = None,
    model: str | None = None,
    metadata: dict | None = None,
) -> AIOperation:
    row = db.get(AIOperation, operation_id)
    if row is None:
        raise ValueError("AI operation not found")
    row.status = "succeeded" if success else "failed"
    row.input_units = input_units
    row.output_units = output_units
    row.duration_ms = duration_ms
    row.estimated_cost_usd = estimated_cost_usd
    row.error_code = error_code
    if provider is not None:
        row.provider = provider
    if model is not None:
        row.model = model
    if metadata is not None:
        current = dict(row.operation_metadata or {})
        current.update(metadata)
        row.operation_metadata = current
    row.completed_at = datetime.now(UTC)
    db.flush()
    return row
