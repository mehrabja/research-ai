"""Provider-neutral tracing hooks (M36). Noop by default."""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager
from typing import Protocol


class Tracer(Protocol):
    def span(
        self, name: str, **attributes: object
    ) -> AbstractContextManager[None]: ...


class NoopTracer:
    @contextmanager
    def span(
        self, name: str, **attributes: object
    ) -> Iterator[None]:
        yield


_tracer: Tracer = NoopTracer()


def get_tracer() -> Tracer:
    return _tracer


def set_tracer(tracer: Tracer | None) -> None:
    global _tracer
    _tracer = tracer if tracer is not None else NoopTracer()


__all__ = ["NoopTracer", "Tracer", "get_tracer", "set_tracer"]
