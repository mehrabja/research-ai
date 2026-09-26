from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.rate_limit_middleware import GlobalRateLimitMiddleware
from app.core.request_context import RequestIdMiddleware


def _app(limit: int) -> FastAPI:
    app = FastAPI()

    @app.get("/x")
    async def x() -> dict:
        return {"ok": True}

    @app.options("/x")
    async def options_x() -> dict:
        return {"ok": True}

    app.add_middleware(
        GlobalRateLimitMiddleware, limit_per_minute=limit
    )
    app.add_middleware(RequestIdMiddleware)
    return app


def test_under_limit() -> None:
    client = TestClient(_app(5))
    for _ in range(5):
        assert client.get("/x").status_code == 200


def test_over_limit_429_contract() -> None:
    client = TestClient(_app(3))
    for _ in range(3):
        client.get("/x")
    r = client.get("/x")
    assert r.status_code == 429
    body = r.json()
    assert body["error"]["code"] == "RATE_LIMITED"
    assert body["error"]["retry_after"] >= 1
    assert int(r.headers["retry-after"]) >= 1


def test_exactly_one_request_id_on_429() -> None:
    client = TestClient(_app(1))
    client.get("/x")
    r = client.get("/x", headers={"X-Request-ID": "rid-429"})
    assert r.status_code == 429
    values = r.headers.get_list("X-Request-ID")
    assert len(values) == 1
    assert values[0] == "rid-429"


def test_options_bypasses_and_returns_200() -> None:
    client = TestClient(_app(1))
    assert client.get("/x").status_code == 200
    assert client.get("/x").status_code == 429

    r = client.options("/x")
    assert r.status_code == 200
    assert r.json() == {"ok": True}

    assert client.get("/x").status_code == 429


def test_options_does_not_consume_budget() -> None:
    client = TestClient(_app(1))
    for _ in range(50):
        assert client.options("/x").status_code == 200
    assert client.get("/x").status_code == 200
    assert client.get("/x").status_code == 429


def test_negative_limit_raises() -> None:
    with pytest.raises(ValueError):
        GlobalRateLimitMiddleware(object(), limit_per_minute=-1)


def test_zero_limit_disables() -> None:
    app = FastAPI()

    @app.get("/y")
    async def y() -> dict:
        return {"ok": True}

    app.add_middleware(
        GlobalRateLimitMiddleware, limit_per_minute=0
    )
    app.add_middleware(RequestIdMiddleware)
    client = TestClient(app)
    for _ in range(20):
        assert client.get("/y").status_code == 200


def test_positive_limit_enabled() -> None:
    client = TestClient(_app(2))
    assert client.get("/x").status_code == 200
    assert client.get("/x").status_code == 200
    assert client.get("/x").status_code == 429
