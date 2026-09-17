"""Login throttling."""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable
from typing import Protocol

from app.core.config import get_settings


class Clock(Protocol):
    def monotonic(self) -> float: ...


class LoginRateLimiter(Protocol):
    def check_email_allowed(self, email_key: str) -> bool: ...
    def check_ip_allowed(self, ip_key: str) -> bool: ...
    def record_failure(self, email_key: str, ip_key: str) -> None: ...
    def record_success(self, email_key: str) -> None: ...


class InMemoryLoginRateLimiter:
    def __init__(
        self,
        *,
        limit: int,
        window_seconds: int,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._limit = limit
        self._window = float(window_seconds)
        self._clock = clock
        self._email_failures: dict[str, deque[float]] = defaultdict(deque)
        self._ip_failures: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def _prune_locked(
        self,
        q: deque[float],
        now: float,
    ) -> None:
        cutoff = now - self._window

        while q and q[0] < cutoff:
            q.popleft()

    def _allowed(
        self,
        failures: dict[str, deque[float]],
        key: str,
    ) -> bool:
        now = self._clock()

        with self._lock:
            self._prune_locked(failures[key], now)
            return len(failures[key]) < self._limit

    def check_email_allowed(self, email_key: str) -> bool:
        return self._allowed(self._email_failures, email_key)

    def check_ip_allowed(self, ip_key: str) -> bool:
        return self._allowed(self._ip_failures, ip_key)

    def record_failure(
        self,
        email_key: str,
        ip_key: str,
    ) -> None:
        now = self._clock()

        with self._lock:
            self._prune_locked(
                self._email_failures[email_key],
                now,
            )
            self._email_failures[email_key].append(now)

            self._prune_locked(
                self._ip_failures[ip_key],
                now,
            )
            self._ip_failures[ip_key].append(now)

    def record_success(self, email_key: str) -> None:
        with self._lock:
            self._email_failures.pop(email_key, None)


_limiter: LoginRateLimiter | None = None
_limiter_lock = threading.Lock()


def get_login_rate_limiter() -> LoginRateLimiter:
    global _limiter

    if _limiter is None:
        with _limiter_lock:
            if _limiter is None:
                settings = get_settings()

                _limiter = InMemoryLoginRateLimiter(
                    limit=settings.login_rate_limit,
                    window_seconds=settings.login_rate_window_seconds,
                )

    return _limiter


def set_login_rate_limiter(
    limiter: LoginRateLimiter | None,
) -> None:
    global _limiter

    with _limiter_lock:
        _limiter = limiter
