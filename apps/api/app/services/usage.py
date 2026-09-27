"""Usage recording helpers.

Two independent subsystems coexist here:

  * ``record_humanization_usage`` — M17.  Writes a row to the
    legacy ``usage_logs`` table (``app.db.models.ops.UsageLog``).
    Used by the post-translation humanization engine and workers.

  * M37 usage metering — writes to the multi-tenant
    ``usage_events`` table (``app.db.models.usage.UsageEvent``).
    Scoped per workspace, idempotent, UTC calendar-month
    aggregation.

The two tables have different ownership models (user-centric vs
workspace-centric) and must not be conflated.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.exceptions import (
    UsageInvalidMetric,
    UsageInvalidQuantity,
    UsageInvalidSourceType,
    UsageWorkspaceMissing,
)
from app.db.models.usage import (
    USAGE_METRICS,
    USAGE_SOURCE_TYPES,
    UsageEvent,
)

# ==========================================================================
# M17 — legacy per-report usage log
# ==========================================================================

def record_humanization_usage(
    *,
    db: Session,
    user_id: uuid.UUID,
    report_id: uuid.UUID,
    phase: str,
    provider: str,
    model: str,
    input_tokens: int | None,
    output_tokens: int | None,
    idempotency_key: str | None = None,
    trace_id: str | None = None,
    log_metadata: dict[str, Any] | None = None,
) -> None:
    """Persist a ``UsageLog`` row.

    M17 helper.  Writes to ``usage_logs`` (user/report scoped).
    Caller owns the surrounding transaction.
    """
    from app.db.models.ops import UsageLog

    db.add(
        UsageLog(
            user_id=user_id,
            report_id=report_id,
            phase=phase,
            provider=provider,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            idempotency_key=idempotency_key,
            trace_id=trace_id,
            log_metadata=log_metadata,
        )
    )
    db.flush()


# ==========================================================================
# M37 — workspace-scoped usage metering
# ==========================================================================

def period_bounds_utc(
    now: datetime | None = None,
) -> tuple[datetime, datetime]:
    """Return ``(start, end)`` of the current UTC calendar month.

    ``start`` is inclusive, ``end`` is exclusive.  Both are
    timezone-aware UTC datetimes.
    """
    ref = now or datetime.now(UTC)
    if ref.tzinfo is None:
        ref = ref.replace(tzinfo=UTC)
    ref = ref.astimezone(UTC)
    start = ref.replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)
    return start, end


def report_created_key(report_id: uuid.UUID) -> str:
    return f"report:{report_id}"


def job_enqueued_key(job_id: uuid.UUID) -> str:
    return f"job:{job_id}"


def file_uploaded_key(file_id: uuid.UUID) -> str:
    return f"file:{file_id}"


def record_event(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    metric: str,
    quantity: int,
    user_id: uuid.UUID | None = None,
    idempotency_key: str | None = None,
    source_type: str | None = None,
    usage_class: str = "internal",
    source_id: uuid.UUID | None = None,
    occurred_at: datetime | None = None,
    metadata: dict[str, Any] | None = None,
) -> UsageEvent:
    """Insert a workspace-scoped usage event.

    * ``quantity`` must be strictly positive.
    * ``idempotency_key IS NULL`` — every call inserts a new row.
    * ``idempotency_key IS NOT NULL`` — the tuple
      ``(workspace_id, metric, idempotency_key)`` is unique; a
      duplicate returns the existing row unchanged.
    * Caller owns the transaction.  A rollback of the caller
      transaction rolls back the usage event too.
    """
    if workspace_id is None:
        raise UsageWorkspaceMissing()
    if metric not in USAGE_METRICS:
        raise UsageInvalidMetric()
    if source_type is not None and source_type not in USAGE_SOURCE_TYPES:
        raise UsageInvalidSourceType()
    if usage_class not in {"provider", "internal", "billable"}:
        raise UsageInvalidSourceType()
    if not isinstance(quantity, int) or quantity <= 0:
        raise UsageInvalidQuantity()

    if occurred_at is None:
        occurred = datetime.now(UTC)
    elif occurred_at.tzinfo is None:
        occurred = occurred_at.replace(tzinfo=UTC)
    else:
        occurred = occurred_at

    base_stmt: Any = pg_insert(UsageEvent).values(
        workspace_id=workspace_id,
        user_id=user_id,
        metric=metric,
        quantity=quantity,
        idempotency_key=idempotency_key,
        source_type=source_type,
        source_id=source_id,
        occurred_at=occurred,
        event_metadata={**(metadata or {}), "usage_class": usage_class},
    )

    # SQLAlchemy 2.0 typing for the
    # ``Insert -> on_conflict_do_nothing -> returning`` chain is
    # not fully modeled; ``Any`` is used to keep mypy happy
    # without altering runtime behavior.
    if idempotency_key is not None:
        stmt: Any = base_stmt.on_conflict_do_nothing(
            index_elements=[
                "workspace_id",
                "metric",
                "idempotency_key",
            ],
            index_where=text("idempotency_key IS NOT NULL"),
        )
    else:
        stmt = base_stmt

    stmt = stmt.returning(UsageEvent.id)

    inserted_id = db.execute(stmt).scalar_one_or_none()
    if inserted_id is not None:
        row = db.get(UsageEvent, inserted_id)
        assert row is not None
        return row

    # Conflict path — only reachable when idempotency_key is set.
    existing = db.execute(
        select(UsageEvent).where(
            UsageEvent.workspace_id == workspace_id,
            UsageEvent.metric == metric,
            UsageEvent.idempotency_key == idempotency_key,
        )
    ).scalar_one()
    return existing


def get_period_usage(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    metric: str,
    period_start: datetime,
    period_end: datetime,
    usage_class: str | None = None,
) -> int:
    """Sum ``quantity`` for ``(workspace, metric)`` in
    ``[period_start, period_end)``.  Half-open interval."""
    if metric not in USAGE_METRICS:
        raise UsageInvalidMetric()
    conditions = [
        UsageEvent.workspace_id == workspace_id,
        UsageEvent.metric == metric,
        UsageEvent.occurred_at >= period_start,
        UsageEvent.occurred_at < period_end,
    ]
    if usage_class is not None:
        if usage_class not in {"provider", "internal", "billable"}:
            raise UsageInvalidSourceType()
        conditions.append(
            UsageEvent.event_metadata["usage_class"].astext == usage_class
        )
    total = db.execute(
        select(func.coalesce(func.sum(UsageEvent.quantity), 0)).where(
            *conditions
        )
    ).scalar_one()
    return int(total)


def get_current_period_usage(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    metric: str,
    now: datetime | None = None,
) -> int:
    """Sum ``quantity`` for the current UTC calendar month."""
    start, end = period_bounds_utc(now)
    return get_period_usage(
        db,
        workspace_id=workspace_id,
        metric=metric,
        period_start=start,
        period_end=end,
    )


__all__ = [
    "file_uploaded_key",
    "get_current_period_usage",
    "get_period_usage",
    "job_enqueued_key",
    "period_bounds_utc",
    "record_event",
    "record_humanization_usage",
    "report_created_key",
]
