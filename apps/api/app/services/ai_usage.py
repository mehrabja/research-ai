"""M39 AI operation usage ledger.

This adapter keeps provider consumption and product/billable metering
explicit while reusing the existing append-only UsageLog/UsageEvent
tables. Provider token counts live in UsageLog; product/billable units
live in UsageEvent metadata and the existing ai_generation_units metric.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.ops import ModelPricing, UsageLog
from app.services.usage import record_event


@dataclass(frozen=True)
class AIUsage:
    operation: str
    provider: str
    model: str
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    request_id: str | None
    duration_ms: int | None
    billable_units: int
    estimated_cost_usd: Decimal | None


def _estimate_cost(
    db: Session,
    *,
    provider: str,
    model: str,
    input_tokens: int | None,
    output_tokens: int | None,
) -> Decimal | None:
    pricing = db.execute(
        select(ModelPricing)
        .where(
            ModelPricing.provider == provider,
            ModelPricing.model == model,
            ModelPricing.effective_to.is_(None),
        )
        .order_by(ModelPricing.effective_from.desc())
        .limit(1)
    ).scalar_one_or_none()
    if pricing is None:
        return None

    # ModelPricing stores the provider/model unit price contract. Existing
    # M37 records are interpreted as USD per token.
    input_cost = (
        Decimal(input_tokens) * pricing.input_price
        if input_tokens is not None
        else Decimal("0")
    )
    output_cost = (
        Decimal(output_tokens) * pricing.output_price
        if output_tokens is not None
        else Decimal("0")
    )
    return input_cost + output_cost


def record_ai_operation(
    db: Session,
    *,
    user_id: uuid.UUID,
    workspace_id: uuid.UUID,
    operation: str,
    provider: str,
    model: str,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    total_tokens: int | None = None,
    request_id: str | None = None,
    duration_ms: int | None = None,
    billable_units: int = 1,
    idempotency_key: str,
    project_id: uuid.UUID | None = None,
    report_id: uuid.UUID | None = None,
    job_id: uuid.UUID | None = None,
    success: bool = True,
    error_code: str | None = None,
) -> AIUsage:
    if billable_units < 0:
        raise ValueError("billable_units cannot be negative")

    estimated_cost = _estimate_cost(
        db,
        provider=provider,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )

    metadata: dict[str, Any] = {
        "operation": operation,
        "provider": provider,
        "model": model,
        "request_id": request_id,
        "duration_ms": duration_ms,
        "total_tokens": total_tokens,
        "project_id": str(project_id) if project_id else None,
        "report_id": str(report_id) if report_id else None,
        "job_id": str(job_id) if job_id else None,
        "success": success,
        "error_code": error_code,
        "estimated_cost_usd": str(estimated_cost)
        if estimated_cost is not None
        else None,
    }

    db.add(
        UsageLog(
            user_id=user_id,
            report_id=report_id,
            phase=operation,
            provider=provider,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            idempotency_key=idempotency_key,
            trace_id=request_id,
            log_metadata=metadata,
            cost_usd_raw=estimated_cost,
        )
    )
    db.flush()

    if billable_units > 0:
        record_event(
            db,
            workspace_id=workspace_id,
            user_id=user_id,
            metric="ai_generation_units",
            quantity=billable_units,
            idempotency_key=f"{idempotency_key}:billable",
            source_type="provider_call",
            metadata={
                "operation": operation,
                "provider": provider,
                "model": model,
                "request_id": request_id,
                "provider_tokens": total_tokens,
                "estimated_cost_usd": str(estimated_cost)
                if estimated_cost is not None
                else None,
            },
        )

    return AIUsage(
        operation=operation,
        provider=provider,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        request_id=request_id,
        duration_ms=duration_ms,
        billable_units=billable_units,
        estimated_cost_usd=estimated_cost,
    )
