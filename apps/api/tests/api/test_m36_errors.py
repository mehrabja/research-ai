"""M36 — Safe error envelope tests."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_unknown_route_does_not_leak_internals() -> None:
    r = client.get("/api/v1/definitely-not-a-real-route")
    text = r.text.lower()
    assert "traceback" not in text
    assert "sqlalchemy" not in text
    assert "password" not in text


def test_404_has_request_id_in_body() -> None:
    r = client.get(
        "/api/v1/definitely-not-a-real-route",
        headers={"X-Request-ID": "rid-404"},
    )
    assert r.status_code == 404
    body = r.json()
    # Structured envelope
    assert body["error"]["request_id"] == "rid-404"
    # Backwards-compatible detail is preserved
    assert "detail" in body


def test_error_response_header_has_request_id() -> None:
    r = client.get(
        "/api/v1/definitely-not-a-real-route",
        headers={"X-Request-ID": "rid-xyz"},
    )
    assert r.headers.get("X-Request-ID") == "rid-xyz"


def test_validation_error_shape() -> None:
    # Posting an obviously invalid body to a known endpoint that
    # requires a Pydantic model.
    r = client.post(
        "/api/v1/auth/login",
        json={},
        headers={"X-Request-ID": "rid-val"},
    )
    assert r.status_code == 422
    body = r.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["request_id"] == "rid-val"
    assert "detail" in body
    assert "errors" in body
