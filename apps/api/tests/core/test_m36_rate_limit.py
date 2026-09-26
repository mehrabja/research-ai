from __future__ import annotations

import pytest

from app.services.general_rate_limit import (
    InMemoryRateLimitBackend,
)


def test_under_limit() -> None:
    b = InMemoryRateLimitBackend()
    for _ in range(5):
        ok, _ = b.hit("k", limit=5, window_seconds=60.0)
        assert ok


def test_over_limit_returns_retry() -> None:
    b = InMemoryRateLimitBackend()
    for _ in range(3):
        b.hit("k", limit=3, window_seconds=60.0)
    ok, retry = b.hit("k", limit=3, window_seconds=60.0)
    assert not ok
    assert retry >= 1


def test_key_isolation() -> None:
    b = InMemoryRateLimitBackend()
    for _ in range(3):
        b.hit("a", limit=3, window_seconds=60.0)
    ok, _ = b.hit("b", limit=3, window_seconds=60.0)
    assert ok


def test_clock_expiry() -> None:
    now = [0.0]
    b = InMemoryRateLimitBackend(clock=lambda: now[0])
    for _ in range(3):
        b.hit("k", limit=3, window_seconds=10.0)
    ok, _ = b.hit("k", limit=3, window_seconds=10.0)
    assert not ok
    now[0] = 11.0
    ok, _ = b.hit("k", limit=3, window_seconds=10.0)
    assert ok


def test_max_keys_bound_enforced() -> None:
    b = InMemoryRateLimitBackend(max_keys=3)
    for i in range(10):
        b.hit(f"k{i}", limit=10, window_seconds=60.0)
    assert b.size() == 3


def test_lru_eviction_order() -> None:
    b = InMemoryRateLimitBackend(max_keys=2)
    b.hit("a", limit=10, window_seconds=60.0)
    b.hit("b", limit=10, window_seconds=60.0)
    b.hit("a", limit=10, window_seconds=60.0)
    b.hit("c", limit=10, window_seconds=60.0)
    assert b.size() == 2


def test_invalid_limit_raises() -> None:
    b = InMemoryRateLimitBackend()
    with pytest.raises(ValueError):
        b.hit("k", limit=0, window_seconds=60.0)
    with pytest.raises(ValueError):
        b.hit("k", limit=-1, window_seconds=60.0)


def test_invalid_window_raises() -> None:
    b = InMemoryRateLimitBackend()
    with pytest.raises(ValueError):
        b.hit("k", limit=1, window_seconds=0.0)
    with pytest.raises(ValueError):
        b.hit("k", limit=1, window_seconds=-1.0)


def test_invalid_max_keys_raises() -> None:
    with pytest.raises(ValueError):
        InMemoryRateLimitBackend(max_keys=0)
    with pytest.raises(ValueError):
        InMemoryRateLimitBackend(max_keys=-5)
