"""Structured audit logging with optional durable persistence."""
from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from app.core.config import get_settings
from app.core.logging import redact
from app.core.request_context import get_request_id

if TYPE_CHECKING:
    from fastapi import Request
    from sqlalchemy.orm import Session

logger = logging.getLogger("audit")

_ALLOWED_FIELDS: frozenset[str] = frozenset({
    "user_id", "project_id", "report_id", "file_id", "job_id", "run_id",
    "workspace_id", "invitation_id", "membership_id", "subscription_id",
    "feature", "limit", "current", "metric", "quantity", "from_role",
    "to_role", "provider", "plan_code", "route", "method", "status_code",
    "category", "reason", "outcome", "resource_type", "resource_id",
})

_SENSITIVE_KEYS = frozenset({
    "token", "secret", "password", "authorization", "cookie",
    "access_token", "refresh_token", "code_verifier", "mfa_secret",
})


def _normalize_event_code(code: str) -> str:
    if not code or not code.replace("_", "").isalnum() or not code.isupper():
        return "UNKNOWN"
    return code


def _uuid(raw: Any) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(raw)) if raw else None
    except (TypeError, ValueError):
        return None


def emit_audit(
    event_code: str,
    *,
    db: Session | None = None,
    request: Request | None = None,
    **fields: Any,
) -> None:
    code = _normalize_event_code(event_code)
    safe: dict[str, Any] = {}
    for key, value in fields.items():
        if key in _SENSITIVE_KEYS:
            continue
        if key not in _ALLOWED_FIELDS:
            continue
        safe[key] = redact(value)

    rid = get_request_id()
    if rid:
        safe["request_id"] = rid

    logger.info("audit_event code=%s", code, extra={"event": code, **safe})

    if db is None or not get_settings().audit_enabled:
        return

    from app.db.models.audit import AuditEvent

    ip_address = None
    user_agent = None
    if request is not None:
        ip_address = getattr(request.client, "host", None)
        user_agent = (request.headers.get("user-agent") or "")[:1000] or None

    structural = {
        "user_id", "workspace_id", "project_id", "request_id",
        "route", "method", "status_code", "outcome", "reason",
        "resource_type", "resource_id",
    }
    metadata = {k: v for k, v in safe.items() if k not in structural}

    db.add(AuditEvent(
        actor_user_id=_uuid(safe.get("user_id")),
        workspace_id=_uuid(safe.get("workspace_id")),
        project_id=_uuid(safe.get("project_id")),
        event_code=code,
        resource_type=str(safe["resource_type"]) if safe.get("resource_type") else None,
        resource_id=str(safe["resource_id"]) if safe.get("resource_id") else None,
        outcome=str(safe.get("outcome") or "success"),
        reason=str(safe["reason"]) if safe.get("reason") is not None else None,
        request_id=rid,
        ip_address=ip_address,
        user_agent=user_agent,
        metadata_json=metadata or None,
        occurred_at=datetime.now(UTC),
    ))


__all__ = ["emit_audit"]
