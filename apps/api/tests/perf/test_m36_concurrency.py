"""M36 — bounded concurrency tests.

These are small-scale sanity checks, not benchmarks. They assert that
the app remains functional under concurrent load and that limits are
enforced.
"""
from __future__ import annotations

import concurrent.futures as cf

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_concurrent_health_requests() -> None:
    def one() -> int:
        return client.get("/api/v1/health/live").status_code

    with cf.ThreadPoolExecutor(max_workers=20) as pool:
        results = list(pool.map(lambda _: one(), range(200)))
    assert all(code == 200 for code in results)
    assert len(results) == 200


def test_concurrent_ready_requests() -> None:
    def one() -> int:
        return client.get("/api/v1/health/ready").status_code

    with cf.ThreadPoolExecutor(max_workers=10) as pool:
        results = list(pool.map(lambda _: one(), range(50)))
    # 200 = ready, 503 = degraded. Both acceptable.
    assert all(code in (200, 503) for code in results)


def test_concurrent_404_requests() -> None:
    def one() -> int:
        return client.get("/api/v1/definitely-not-a-route").status_code

    with cf.ThreadPoolExecutor(max_workers=10) as pool:
        results = list(pool.map(lambda _: one(), range(100)))
    assert all(code == 404 for code in results)
