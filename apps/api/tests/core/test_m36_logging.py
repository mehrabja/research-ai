"""M36 — Structured logging and redaction tests."""
from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime

from app.core.logging import (
    JsonFormatter,
    RequestContextFilter,
    redact,
)
from app.core.request_context import (
    reset_request_id,
    set_request_id,
)


def _record(
    message: str, **extra: object
) -> logging.LogRecord:
    rec = logging.LogRecord(
        name="t",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=message,
        args=(),
        exc_info=None,
    )
    for k, v in extra.items():
        setattr(rec, k, v)
    RequestContextFilter().filter(rec)
    return rec


def test_json_serializes_uuid_and_datetime() -> None:
    rid = uuid.uuid4()
    rec = _record(
        "hi",
        user_id=rid,
        run_id=datetime(2024, 1, 1, tzinfo=UTC),
    )
    payload = json.loads(JsonFormatter().format(rec))
    assert payload["user_id"] == str(rid)
    assert payload["run_id"].startswith("2024-01-01")


def test_json_serializes_unserializable_safely() -> None:
    class Weird:
        pass

    rec = _record("hi", run_id=Weird())
    payload = json.loads(JsonFormatter().format(rec))
    assert isinstance(payload["run_id"], str)


def test_json_includes_request_id_from_contextvar() -> None:
    token = set_request_id("rid-abc")
    try:
        rec = _record("hello")
        payload = json.loads(JsonFormatter().format(rec))
        assert payload["request_id"] == "rid-abc"
    finally:
        reset_request_id(token)


def test_redact_removes_secret_dict_keys() -> None:
    data = {
        "authorization": "Bearer abc",
        "password": "hunter2",
        "nested": {"api_key": "xyz"},
        "database_url": "postgresql://u:p@host/db",
    }
    out = redact(data)
    assert out["authorization"] == "***"
    assert out["password"] == "***"
    assert out["nested"]["api_key"] == "***"
    assert out["database_url"] == "***"


def test_redact_masks_known_substring_in_strings() -> None:
    assert redact("postgresql://u:p@host/db") == "***"
    assert redact("Authorization: Bearer SECRET") == "***"


def test_json_formatter_redacts_bearer_in_message() -> None:
    rec = _record("auth header Bearer abc123 sent")
    payload = json.loads(JsonFormatter().format(rec))
    assert "abc123" not in payload["message"]


def test_json_formatter_does_not_raise_on_bad_object() -> None:
    class Bad:
        def __repr__(self) -> str:
            raise RuntimeError("nope")

    rec = _record("x", run_id=Bad())
    # Must not raise:
    out = JsonFormatter().format(rec)
    assert "x" in out
