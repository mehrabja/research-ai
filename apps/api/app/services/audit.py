"""Lightweight audit-event emitter (M36).

Reuses the existing structured logger and redaction layer. This module
does NOT create a new audit table — it emits structured log lines that
deployments can route to a SIEM or log aggregator.

Event codes are UPPERCASE to keep them bounded and greppable. Any
unknown code is replaced with ``UNKNOWN`` so an arbitrary string
cannot become an event name.

Allowed fields are a fixed allowlist. Unknown fields are dropped so
that accidental PII cannot leak through this channel.
"""
from __future__ import annotations

import logging
from typing import Any

from app.core.logging import redact
from app.core.request_context import get_request_id

logger = logging.getLogger("audit")

_ALLOWED_FIELDS: frozenset[str] = frozenset(
    {
        # M36 base
        "user_id",
        "project_id",
        "report_id",
        "file_id",
        "job_id",
        "run_id",
        "route",
        "method",
        "status_code",
        "category",
        "reason",
        "outcome",
        # M37 — SaaS foundation
        "workspace_id",
        "invitation_id",
        "membership_id",
        "subscription_id",
        "feature",
        "limit",
        "current",
        "metric",
        "quantity",
        "from_role",
        "to_role",
        "provider",
        "plan_code",
    }
)


def _normalize_event_code(code: str) -> str:
    if not code or not code.replace("_", "").isalnum():
        return "UNKNOWN"
    if not code.isupper():
        return "UNKNOWN"
    return code


def emit_audit(event_code: str, **fields: Any) -> None:
    """Emit a single audit event.

    The event is written to the ``audit`` logger with ``extra`` so the
    JSON formatter (Chunk 1) picks it up. Any field value is passed
    through ``redact`` so bearer tokens / DB URLs cannot leak.
    """
    code = _normalize_event_code(event_code)
    safe: dict[str, Any] = {}
    for key, value in fields.items():
        if key not in _ALLOWED_FIELDS:
            continue
        safe[key] = redact(value)

    rid = get_request_id()
    if rid:
        safe["request_id"] = rid

    logger.info(
        "audit_event code=%s",
        code,
        extra={"event": code, **safe},
    )


__all__ = ["emit_audit"]
