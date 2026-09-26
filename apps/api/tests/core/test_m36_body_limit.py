from __future__ import annotations

import asyncio

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.core.body_limit import BodyLimitMiddleware
from app.core.request_context import RequestIdMiddleware


def _app(max_bytes: int):
    app = FastAPI()
    calls = {"n": 0}

    @app.post("/echo")
    async def echo(request: Request) -> dict:
        calls["n"] += 1
        return {"len": len(await request.body())}

    @app.post("/stream")
    async def stream(request: Request) -> dict:
        calls["n"] += 1
        total = 0
        async for chunk in request.stream():
            total += len(chunk)
        return {"total": total}

    @app.delete("/del")
    async def delete(request: Request) -> dict:
        calls["n"] += 1
        return {"len": len(await request.body())}

    @app.get("/ping")
    async def ping() -> dict:
        return {"ok": True}

    app.add_middleware(BodyLimitMiddleware, max_bytes=max_bytes)
    app.add_middleware(RequestIdMiddleware)
    return app, calls


def _direct_call(scope_headers):
    sent: list[dict] = []

    async def downstream(scope, receive, send):
        raise AssertionError("downstream must not run")

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(m):
        sent.append(m)

    mw = BodyLimitMiddleware(downstream, max_bytes=1024)
    scope = {
        "type": "http",
        "method": "POST",
        "headers": scope_headers,
    }
    asyncio.run(mw(scope, receive, send))
    return sent


def test_get_with_no_body_passes() -> None:
    app, _ = _app(64)
    assert TestClient(app).get("/ping").status_code == 200


def test_content_length_exact_max_allowed() -> None:
    app, calls = _app(64)
    r = TestClient(app).post("/echo", content=b"a" * 64)
    assert r.status_code == 200
    assert calls["n"] == 1


def test_content_length_max_plus_one_413() -> None:
    app, calls = _app(64)
    r = TestClient(app).post("/echo", content=b"a" * 65)
    assert r.status_code == 413
    assert calls["n"] == 0
    body = r.json()
    assert body["error"]["code"] == "REQUEST_TOO_LARGE"
    assert body["error"]["max_bytes"] == 64


def test_streaming_exact_max() -> None:
    app, _ = _app(64)

    def gen():
        for _ in range(4):
            yield b"x" * 16

    assert (
        TestClient(app).post("/stream", content=gen()).status_code == 200
    )


def test_streaming_overflow_endpoint_not_run() -> None:
    app, calls = _app(64)

    def gen():
        for _ in range(5):
            yield b"x" * 16

    r = TestClient(app).post("/stream", content=gen())
    assert r.status_code == 413
    assert calls["n"] == 0


def test_delete_with_body_enforced() -> None:
    app, calls = _app(16)
    r = TestClient(app).request("DELETE", "/del", content=b"a" * 100)
    assert r.status_code == 413
    assert calls["n"] == 0


def test_exactly_one_request_id_on_413() -> None:
    app, _ = _app(16)
    r = TestClient(app).post(
        "/echo",
        content=b"z" * 100,
        headers={"X-Request-ID": "rid-413"},
    )
    values = r.headers.get_list("X-Request-ID")
    assert len(values) == 1
    assert values[0] == "rid-413"


@pytest.mark.parametrize("cl", [b"0", b"1", b"10", b"0010", b"00000064"])
def test_valid_content_length_accepted(cl: bytes) -> None:
    async def _run() -> None:
        sent: list[dict] = []

        async def downstream(scope, receive, send):
            await send({"type": "http.response.start",
                        "status": 204, "headers": []})
            await send({"type": "http.response.body", "body": b""})

        async def receive():
            return {"type": "http.request", "body": b"x" * 10,
                    "more_body": False}

        async def send(m):
            sent.append(m)

        mw = BodyLimitMiddleware(downstream, max_bytes=1024)
        scope = {
            "type": "http",
            "method": "POST",
            "headers": [(b"content-length", cl)],
        }
        await mw(scope, receive, send)
        assert sent[0]["status"] == 204

    asyncio.run(_run())


@pytest.mark.parametrize(
    "cl",
    [
        b"+10",
        b"-1",
        b" 10 ",
        b"10 ",
        b" 10",
        b"1e3",
        b"0x10",
        b"10x",
        b"",
        b"   ",
        b"10\n",
    ],
)
def test_strict_content_length_rejected(cl: bytes) -> None:
    sent = _direct_call([(b"content-length", cl)])
    assert sent[0]["status"] == 400


def test_duplicate_identical_accepted() -> None:
    async def _run() -> None:
        sent: list[dict] = []

        async def downstream(scope, receive, send):
            await send({"type": "http.response.start",
                        "status": 204, "headers": []})
            await send({"type": "http.response.body", "body": b""})

        async def receive():
            return {"type": "http.request", "body": b"x" * 10,
                    "more_body": False}

        async def send(m):
            sent.append(m)

        mw = BodyLimitMiddleware(downstream, max_bytes=1024)
        scope = {
            "type": "http",
            "method": "POST",
            "headers": [
                (b"content-length", b"10"),
                (b"content-length", b"10"),
            ],
        }
        await mw(scope, receive, send)
        assert sent[0]["status"] == 204

    asyncio.run(_run())


@pytest.mark.parametrize(
    "headers",
    [
        [(b"content-length", b"10"), (b"content-length", b"20")],
        [(b"content-length", b"10"), (b"content-length", b"10x")],
        [(b"content-length", b"10"), (b"content-length", b"10 ")],
        [(b"content-length", b"10"), (b"content-length", b"+10")],
        [(b"content-length", b"10"), (b"content-length", b"")],
    ],
)
def test_duplicate_conflicting_rejected(headers) -> None:
    sent = _direct_call(headers)
    assert sent[0]["status"] == 400


def test_huge_content_length_rejected() -> None:
    sent = _direct_call(
        [(b"content-length", str(10**15).encode("latin-1"))]
    )
    assert sent[0]["status"] == 400


@pytest.mark.parametrize("bad", [0, -1])
def test_body_limit_invalid_max_bytes(bad: int) -> None:
    with pytest.raises(ValueError):
        BodyLimitMiddleware(object(), max_bytes=bad)
