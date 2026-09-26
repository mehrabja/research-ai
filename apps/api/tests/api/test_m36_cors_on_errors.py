from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from app.core.body_limit import BodyLimitMiddleware
from app.core.rate_limit_middleware import GlobalRateLimitMiddleware
from app.core.request_context import RequestIdMiddleware

ORIGIN = "https://example.com"


def _app() -> FastAPI:
    app = FastAPI()

    @app.get("/ping")
    async def ping() -> dict:
        return {"ok": True}

    @app.post("/echo")
    async def echo(request: Request) -> dict:
        return {"len": len(await request.body())}

    # add_middleware PREPENDS. Effective outer→inner:
    #   RequestId → CORS → BodyLimit → GlobalRateLimit → app
    app.add_middleware(
        GlobalRateLimitMiddleware, limit_per_minute=2
    )
    app.add_middleware(BodyLimitMiddleware, max_bytes=8)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[ORIGIN],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestIdMiddleware)
    return app


def test_cors_on_normal() -> None:
    r = TestClient(_app()).get("/ping", headers={"Origin": ORIGIN})
    assert r.status_code == 200
    assert r.headers.get("access-control-allow-origin") == ORIGIN


def test_cors_on_400_invalid_content_length() -> None:
    r = TestClient(_app()).post(
        "/echo",
        content=b"x",
        headers={
            "Origin": ORIGIN,
            "Content-Length": "not-a-number",
        },
    )
    assert r.status_code == 400
    assert r.headers.get("access-control-allow-origin") == ORIGIN


def test_cors_on_413() -> None:
    r = TestClient(_app()).post(
        "/echo", content=b"x" * 100, headers={"Origin": ORIGIN}
    )
    assert r.status_code == 413
    assert r.headers.get("access-control-allow-origin") == ORIGIN


def test_cors_on_429() -> None:
    client = TestClient(_app())
    client.get("/ping", headers={"Origin": ORIGIN})
    client.get("/ping", headers={"Origin": ORIGIN})
    r = client.get("/ping", headers={"Origin": ORIGIN})
    assert r.status_code == 429
    assert r.headers.get("access-control-allow-origin") == ORIGIN
