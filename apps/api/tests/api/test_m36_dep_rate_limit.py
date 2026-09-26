from __future__ import annotations

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.api.rate_limit_deps import (
    RateLimitedAppError,
    enforce_ip_rate_limit,
)
from app.core.config import get_settings
from app.core.error_handlers import install_error_handlers
from app.core.request_context import RequestIdMiddleware


def _app(category: str, setting_name: str) -> FastAPI:
    app = FastAPI()
    install_error_handlers(app)

    @app.get(
        "/x",
        dependencies=[
            Depends(
                enforce_ip_rate_limit(
                    category, setting_name=setting_name
                )
            )
        ],
    )
    async def x() -> dict:
        return {"ok": True}

    app.add_middleware(RequestIdMiddleware)
    return app


def test_dep_rate_limit_blocks(monkeypatch) -> None:
    settings = get_settings()
    original = settings.rate_limit_auth_per_minute
    monkeypatch.setattr(
        settings, "rate_limit_auth_per_minute", 2, raising=False
    )
    try:
        client = TestClient(
            _app("x", "rate_limit_auth_per_minute")
        )
        assert client.get("/x").status_code == 200
        assert client.get("/x").status_code == 200
        r = client.get("/x")
        assert r.status_code == 429
        body = r.json()
        assert body["error"]["code"] == "RATE_LIMITED"
        assert body["error"]["retry_after"] >= 1
        assert int(r.headers["retry-after"]) >= 1
    finally:
        settings.rate_limit_auth_per_minute = original


def test_dep_429_request_id_and_retry_after() -> None:
    app = FastAPI()
    install_error_handlers(app)
    app.add_middleware(RequestIdMiddleware)

    @app.get("/boom")
    async def boom() -> dict:
        raise RateLimitedAppError(retry_after=42)

    r = TestClient(app).get(
        "/boom", headers={"X-Request-ID": "rid-dep"}
    )
    assert r.status_code == 429
    assert r.headers["retry-after"] == "42"
    assert r.json()["error"]["retry_after"] == 42
    values = r.headers.get_list("X-Request-ID")
    assert len(values) == 1
    assert values[0] == "rid-dep"
