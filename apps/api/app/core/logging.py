"""Structured logging foundation (M36).

Backwards compatible with the original ``configure_logging(level)``
signature. Adds:

  * optional JSON output (``fmt="json"``)
  * safe serialization of common Python objects
  * best-effort redaction of sensitive values
  * request-ID injection via ``contextvars``

Logging must never crash the application: any serialization failure
degrades to a bounded safe string.
"""
from __future__ import annotations

import json
import logging
import re
import sys
from datetime import UTC, date, datetime
from enum import Enum
from typing import Any
from uuid import UUID

from app.core.request_context import get_request_id

_TEXT_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"

_STRUCTURED_FIELDS = (
    "job_id",
    "run_id",
    "user_id",
    "project_id",
    "report_id",
    "event",
)

# Exact keys that are always redacted in structured dicts.
_REDACTED_KEYS = frozenset(
    {
        "authorization",
        "password",
        "passwd",
        "token",
        "access_token",
        "refresh_token",
        "api_key",
        "apikey",
        "secret",
        "secret_key",
        "jwt_secret",
        "jwt_secret_key",
        "cookie",
        "set-cookie",
        "x-api-key",
        "database_url",
    }
)

# Substrings that trigger full redaction of a string value.
_REDACTED_SUBSTRINGS = (
    "bearer ",
    "postgres://",
    "postgresql://",
    "postgresql+psycopg://",
)

_REDACTED_PATTERNS = (
    re.compile(r"(?i)\bsk-or-v1-[A-Za-z0-9._-]{16,}\b"),
    re.compile(r"(?i)\bsk-[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"(?i)\bwhsec_[A-Za-z0-9_-]{16,}\b"),
)


def _safe_serialize(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    try:
        return str(value)
    except Exception:
        return "<unserializable>"


def redact(value: Any) -> Any:
    """Best-effort redaction of sensitive values."""
    if isinstance(value, dict):
        out: dict[Any, Any] = {}
        for k, v in value.items():
            if str(k).lower() in _REDACTED_KEYS:
                out[k] = "***"
            else:
                out[k] = redact(v)
        return out
    if isinstance(value, (list, tuple)):
        return [redact(v) for v in value]
    if isinstance(value, str):
        low = value.lower()
        if any(s in low for s in _REDACTED_SUBSTRINGS):
            return "***"
        if any(pattern.search(value) for pattern in _REDACTED_PATTERNS):
            return "***"
        return value
    return value


class RequestContextFilter(logging.Filter):
    """Populate ``record.request_id`` from the contextvar."""

    def filter(self, record: logging.LogRecord) -> bool:
        if not getattr(record, "request_id", None):
            record.request_id = get_request_id() or "-"
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(
                record.created, tz=UTC
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": redact(record.getMessage()),
            "request_id": getattr(record, "request_id", "-"),
        }
        for key in _STRUCTURED_FIELDS:
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = _safe_serialize(value)
        if record.exc_info:
            try:
                payload["exc"] = redact(
                    self.formatException(record.exc_info)
                )
            except Exception:
                payload["exc"] = "<unformattable>"
        try:
            return json.dumps(payload, ensure_ascii=False)
        except Exception:
            # Never raise from logging.
            return json.dumps(
                {
                    "ts": payload.get("ts", ""),
                    "level": payload.get("level", "INFO"),
                    "logger": payload.get("logger", "?"),
                    "message": "<unserializable>",
                }
            )


class TextFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        try:
            base = super().format(record)
        except Exception:
            base = (
                f"{record.levelname} {record.name}: <unformattable>"
            )
        rid = getattr(record, "request_id", "-")
        if rid and rid != "-":
            return f"{base} request_id={rid}"
        return base


_configured = False


def configure_logging(
    level: str = "INFO",
    *,
    fmt: str = "text",
    force: bool = False,
) -> None:
    """Configure root logging.

    Backwards compatible with the original ``configure_logging(level)``
    call. If the root logger already has handlers (for example under
    pytest capture or a hosting platform), configuration is skipped
    unless ``force=True``.
    """
    global _configured

    root = logging.getLogger()
    root.setLevel(level.upper())

    if _configured and not force:
        return

    if root.handlers and not force:
        _configured = True
        return

    for handler in list(root.handlers):
        root.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(RequestContextFilter())

    if fmt == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(TextFormatter(_TEXT_FORMAT))

    root.addHandler(handler)
    _configured = True


__all__ = [
    "JsonFormatter",
    "RequestContextFilter",
    "TextFormatter",
    "configure_logging",
    "redact",
]
