"""General-purpose rate limiting infrastructure (M36).

``InMemoryRateLimitBackend`` is per-process only. Multi-replica
deployments MUST swap it for a shared backend (e.g. Redis). The
interface is deliberately narrow so the swap is mechanical.
"""
from __future__ import annotations

import threading
import time
from collections import OrderedDict, deque
from collections.abc import Callable
from typing import Protocol


class RateLimitBackend(Protocol):
    def hit(
        self, key: str, *, limit: int, window_seconds: float
    ) -> tuple[bool, int]: ...

    def reset(self) -> None: ...

    def size(self) -> int: ...


class InMemoryRateLimitBackend:
    """Sliding-window, bounded-cardinality rate limiter.

    Per-process only. When ``max_keys`` is reached, the least-recently
    used key is evicted (LRU). Eviction means a new request from that
    key starts with a fresh window — documented behaviour.
    """

    def __init__(
        self,
        *,
        max_keys: int = 100_000,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if (
            not isinstance(max_keys, int)
            or isinstance(max_keys, bool)
            or max_keys < 1
        ):
            raise ValueError("max_keys must be an integer >= 1")
        self._max_keys = max_keys
        self._clock = clock
        self._buckets: OrderedDict[str, deque[float]] = OrderedDict()
        self._lock = threading.Lock()

    def hit(
        self, key: str, *, limit: int, window_seconds: float
    ) -> tuple[bool, int]:
        if (
            not isinstance(limit, int)
            or isinstance(limit, bool)
            or limit < 1
        ):
            raise ValueError("limit must be an integer >= 1")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be > 0")

        now = self._clock()
        cutoff = now - window_seconds
        with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None:
                if len(self._buckets) >= self._max_keys:
                    self._buckets.popitem(last=False)
                bucket = deque()
                self._buckets[key] = bucket
            else:
                self._buckets.move_to_end(key)

            while bucket and bucket[0] < cutoff:
                bucket.popleft()

            if len(bucket) >= limit:
                retry_after = max(
                    1, int(window_seconds - (now - bucket[0]))
                )
                return False, retry_after
            bucket.append(now)
            return True, 0

    def reset(self) -> None:
        with self._lock:
            self._buckets.clear()

    def size(self) -> int:
        with self._lock:
            return len(self._buckets)


_backend: RateLimitBackend = InMemoryRateLimitBackend()
_backend_lock = threading.Lock()


def get_rate_limit_backend() -> RateLimitBackend:
    return _backend


def set_rate_limit_backend(backend: RateLimitBackend | None) -> None:
    global _backend
    with _backend_lock:
        _backend = (
            backend if backend is not None
            else InMemoryRateLimitBackend()
        )


def reset_rate_limit_backend() -> None:
    _backend.reset()


__all__ = [
    "InMemoryRateLimitBackend",
    "RateLimitBackend",
    "get_rate_limit_backend",
    "reset_rate_limit_backend",
    "set_rate_limit_backend",
]
