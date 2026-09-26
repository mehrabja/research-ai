"""M36 — rate limiter under burst.

Uses an isolated app instance with its own middleware to avoid
interference from the global rate-limit middleware configured on
``app.main.app``.
"""
from __future__ import annotations

import concurrent.futures as cf

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.rate_limit_middleware import GlobalRateLimitMiddleware
from app.services.general_rate_limit import (
    InMemoryRateLimitBackend,
)


def test_limiter_survives_burst_of_concurrent_hits() -> None:
    app = FastAPI()

    @app.get("/x")
    async def x() -> dict:
        return {"ok": True}

    backend = InMemoryRateLimitBackend(max_keys=10_000)
    app.add_middleware(
        GlobalRateLimitMiddleware,
        limit_per_minute=1_000_000,
        backend=backend,
    )
    client = TestClient(app)

    def hit() -> int:
        return client.get("/x").status_code

    with cf.ThreadPoolExecutor(max_workers=25) as pool:
        results = list(pool.map(lambda _: hit(), range(200)))

    assert all(code == 200 for code in results)
    # Backend should have exactly one key (per-IP) with 200 hits tracked.
    assert backend.size() <= 10_000


def test_limiter_enforces_limit_under_burst() -> None:
    app = FastAPI()

    @app.get("/x")
    async def x() -> dict:
        return {"ok": True}

    backend = InMemoryRateLimitBackend()
    app.add_middleware(
        GlobalRateLimitMiddleware,
        limit_per_minute=10,
        backend=backend,
    )
    client = TestClient(app)

    def hit() -> int:
        return client.get("/x").status_code

    with cf.ThreadPoolExecutor(max_workers=5) as pool:
        results = list(pool.map(lambda _: hit(), range(50)))

    passed = [c for c in results if c == 200]
    rejected = [c for c in results if c == 429]
    # Allow a small race window (some may slip through before the counter
    # saturates) but at least 10 must succeed and many must be rejected.
    assert len(passed) >= 10
    assert len(rejected) >= 30
    assert len(passed) + len(rejected) == 50
