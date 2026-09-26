"""M36 — logging privacy tests.

Verifies that sensitive values never appear in emitted log output.
"""
from __future__ import annotations

import json
import logging

from app.core.logging import (
    JsonFormatter,
    RequestContextFilter,
    redact,
)


def _record(msg: str, **extra) -> logging.LogRecord:
    rec = logging.LogRecord(
        name="t",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=msg,
        args=(),
        exc_info=None,
    )
    for k, v in extra.items():
        setattr(rec, k, v)
    RequestContextFilter().filter(rec)
    return rec


def test_bearer_token_in_message_is_masked() -> None:
    rec = _record("Authorization: Bearer SECRET_TOKEN_VALUE")
    out = JsonFormatter().format(rec)
    assert "SECRET_TOKEN_VALUE" not in out


def test_db_url_in_message_is_masked() -> None:
    rec = _record(
        "connecting postgresql://user:pw@host:5432/db"
    )
    out = JsonFormatter().format(rec)
    assert "pw@host" not in out


def test_password_field_masked() -> None:
    rec = _record("login attempt", password="hunter2")
    # JsonFormatter only serializes a fixed set of structured fields,
    # so arbitrary extras are not emitted at all.
    out = JsonFormatter().format(rec)
    assert "hunter2" not in out


def test_redact_masks_nested_secret_dict() -> None:
    data = {
        "outer": {
            "authorization": "Bearer abc",
            "db": "postgresql://u:p@host/db",
        }
    }
    out = redact(data)
    assert out["outer"]["authorization"] == "***"
    assert out["outer"]["db"] == "***"


def test_redact_passes_through_safe_values() -> None:
    assert redact("hello world") == "hello world"
    assert redact(42) == 42
    assert redact({"a": 1}) == {"a": 1}


def test_json_output_parses() -> None:
    rec = _record(
        "safe",
        user_id="u",
        run_id="r",
    )
    payload = json.loads(JsonFormatter().format(rec))
    assert payload["message"] == "safe"
    assert payload["user_id"] == "u"
