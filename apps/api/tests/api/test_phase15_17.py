"""Phase 15-17 security, observability, release-gate, and smoke contracts."""
from __future__ import annotations

import json
import logging

from fastapi.testclient import TestClient

from app.core.logging import JsonFormatter, redact
from app.core.request_context import sanitize_request_id
from app.main import app

client = TestClient(app)


def test_request_id_and_security_headers_are_present() -> None:
    response = client.get(
        "/api/v1/health/live",
        headers={"X-Request-ID": "phase15-test.01"},
    )

    assert response.status_code == 200
    assert response.json() == {"status": "alive"}
    assert response.headers["X-Request-ID"] == "phase15-test.01"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert response.headers["Cross-Origin-Opener-Policy"] == "same-origin"
    assert response.headers["Cross-Origin-Resource-Policy"] == "same-origin"


def test_invalid_request_id_is_replaced_with_safe_identifier() -> None:
    response = client.get(
        "/api/v1/health/live",
        headers={"X-Request-ID": "<script>alert(1)</script>"},
    )

    request_id = response.headers["X-Request-ID"]
    assert response.status_code == 200
    assert request_id != "<script>alert(1)</script>"
    assert sanitize_request_id(request_id) == request_id
    assert len(request_id) <= 128


def test_logging_redacts_tokens_and_connection_strings() -> None:
    payload = {
        "authorization": "Bearer super-secret-token",
        "api_key": "sk-or-v1-1234567890abcdef",
        "nested": {
            "database_url": "postgresql+psycopg://user:secret@db/app",
        },
    }

    redacted = redact(payload)

    assert redacted["authorization"] == "***"
    assert redacted["api_key"] == "***"
    assert redacted["nested"]["database_url"] == "***"


def test_json_formatter_includes_request_and_event_without_secrets() -> None:
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="provider completed",
        args=(),
        exc_info=None,
    )
    record.request_id = "phase15-json"
    record.event = "request_complete"

    output = formatter.format(record)
    body = json.loads(output)

    assert body["request_id"] == "phase15-json"
    assert body["event"] == "request_complete"
    assert body["message"] == "provider completed"
    assert "sk-or-v1" not in output
