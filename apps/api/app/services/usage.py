"""M17 — Usage recording helper.

VERIFY: field names against actual UsageLog model.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session


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
    """Persist a UsageLog row. Caller owns the surrounding transaction."""
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
