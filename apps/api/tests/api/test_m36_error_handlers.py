from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.rate_limit_deps import RateLimitedAppError
from app.core.error_handlers import install_error_handlers
from app.core.exceptions import AppError
from app.core.request_context import RequestIdMiddleware


def _app() -> FastAPI:
    app = FastAPI()
    install_error_handlers(app)
    app.add_middleware(RequestIdMiddleware)

    @app.get("/boom429")
    async def boom429() -> dict:
        raise RateLimitedAppError(retry_after=17)

    @app.get("/boom500")
    async def boom500() -> dict:
        raise AppError("something bad", code="SOMETHING")

    return app


def test_rate_limited_error_contract() -> None:
    client = TestClient(_app())
    r = client.get(
        "/boom429", headers={"X-Request-ID": "rid-429"}
    )
    assert r.status_code == 429
    assert r.headers["retry-after"] == "17"
    body = r.json()
    assert body["error"]["code"] == "RATE_LIMITED"
    assert body["error"]["retry_after"] == 17
    assert body["error"]["request_id"] == "rid-429"
    assert len(r.headers.get_list("X-Request-ID")) == 1


def test_non_429_not_affected() -> None:
    client = TestClient(_app())
    r = client.get("/boom500")
    assert r.status_code == 500
    assert "retry-after" not in {k.lower() for k in r.headers}
    assert "retry_after" not in r.json()["error"]
