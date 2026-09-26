"""M36 — Request ID middleware tests."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_response_has_request_id_header() -> None:
    r = client.get("/api/v1/health/live")
    assert r.status_code == 200
    assert r.headers.get("X-Request-ID")


def test_incoming_request_id_is_echoed() -> None:
    r = client.get(
        "/api/v1/health/live",
        headers={"X-Request-ID": "abc-123"},
    )
    assert r.headers.get("X-Request-ID") == "abc-123"


def test_malformed_incoming_id_is_replaced() -> None:
    r = client.get(
        "/api/v1/health/live",
        headers={"X-Request-ID": "bad value"},
    )
    assert r.headers.get("X-Request-ID") != "bad value"
    assert r.headers.get("X-Request-ID")


def test_oversized_incoming_id_is_replaced() -> None:
    big = "a" * 500
    r = client.get(
        "/api/v1/health/live",
        headers={"X-Request-ID": big},
    )
    assert r.headers.get("X-Request-ID") != big


def test_exactly_one_request_id_header() -> None:
    r = client.get("/api/v1/health/live")
    values = r.headers.get_list("X-Request-ID")
    assert len(values) == 1
