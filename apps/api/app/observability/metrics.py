"""Provider-neutral metrics interface (M36).

The default implementation is in-memory and intended for local dev and
tests ONLY. It is NOT durable production metrics and no business
behaviour may depend on its state.

Labels MUST have bounded cardinality. Never use:
  * request IDs
  * raw UUIDs
  * free-text error messages
  * manuscript content
as label values.
"""
from __future__ import annotations

import threading
from collections import defaultdict
from typing import Protocol


class MetricsBackend(Protocol):
    def incr(
        self,
        name: str,
        *,
        labels: dict[str, str] | None = None,
        value: float = 1.0,
    ) -> None: ...

    def observe(
        self,
        name: str,
        value: float,
        *,
        labels: dict[str, str] | None = None,
    ) -> None: ...


class NoopMetrics:
    def incr(
        self,
        name: str,
        *,
        labels: dict[str, str] | None = None,
        value: float = 1.0,
    ) -> None:
        return None

    def observe(
        self,
        name: str,
        value: float,
        *,
        labels: dict[str, str] | None = None,
    ) -> None:
        return None


class InMemoryMetrics:
    """Thread-safe in-memory registry for local dev and tests."""

    def __init__(self) -> None:
        self._counters: dict[str, float] = defaultdict(float)
        self._observations: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def incr(
        self,
        name: str,
        *,
        labels: dict[str, str] | None = None,
        value: float = 1.0,
    ) -> None:
        key = self._key(name, labels)
        with self._lock:
            self._counters[key] += value

    def observe(
        self,
        name: str,
        value: float,
        *,
        labels: dict[str, str] | None = None,
    ) -> None:
        key = self._key(name, labels)
        with self._lock:
            self._observations[key].append(float(value))

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            return {
                "counters": dict(self._counters),
                "observations": {
                    k: list(v)
                    for k, v in self._observations.items()
                },
            }

    def reset(self) -> None:
        with self._lock:
            self._counters.clear()
            self._observations.clear()

    @staticmethod
    def _key(
        name: str, labels: dict[str, str] | None
    ) -> str:
        if not labels:
            return name
        parts = ",".join(
            f"{k}={v}" for k, v in sorted(labels.items())
        )
        return f"{name}{{{parts}}}"


_metrics: MetricsBackend = InMemoryMetrics()


def get_metrics() -> MetricsBackend:
    return _metrics


def set_metrics(backend: MetricsBackend | None) -> None:
    global _metrics
    _metrics = backend if backend is not None else InMemoryMetrics()


__all__ = [
    "InMemoryMetrics",
    "MetricsBackend",
    "NoopMetrics",
    "get_metrics",
    "set_metrics",
]
