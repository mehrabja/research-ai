"""M36 — audit emitter tests."""
from __future__ import annotations

import json
import logging

import pytest

from app.core.logging import JsonFormatter, RequestContextFilter
from app.services.audit import emit_audit


class _Capture(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


@pytest.fixture()
def capture(monkeypatch) -> _Capture:
    logger = logging.getLogger("audit")
    handler = _Capture()
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    yield handler
    logger.removeHandler(handler)


def test_emits_record_with_code(capture: _Capture) -> None:
    emit_audit("AUTH_FAILURE", user_id="u1", route="/x")
    assert len(capture.records) == 1
    rec = capture.records[0]
    assert rec.__dict__.get("event") == "AUTH_FAILURE"
    assert rec.__dict__.get("user_id") == "u1"
    assert rec.__dict__.get("route") == "/x"


def test_unknown_fields_dropped(capture: _Capture) -> None:
    emit_audit("RATE_LIMITED", password="hunter2", token="abc")
    rec = capture.records[0]
    assert "password" not in rec.__dict__
    assert "token" not in rec.__dict__


def test_lowercase_code_normalized(capture: _Capture) -> None:
    emit_audit("auth_failure")
    assert capture.records[0].__dict__.get("event") == "UNKNOWN"


def test_empty_code_normalized(capture: _Capture) -> None:
    emit_audit("")
    assert capture.records[0].__dict__.get("event") == "UNKNOWN"


def test_json_formatter_serializes_audit(
    capture: _Capture,
) -> None:
    emit_audit("RATE_LIMITED", user_id="u1", reason="ip")
    rec = capture.records[0]
    RequestContextFilter().filter(rec)
    payload = json.loads(JsonFormatter().format(rec))
    assert payload["event"] == "RATE_LIMITED"
    assert payload["user_id"] == "u1"
