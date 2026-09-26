"""Job handler registry."""
from __future__ import annotations

import logging
from collections.abc import Callable

from app.domain.jobs import JobContext

logger = logging.getLogger(__name__)

JobHandler = Callable[[JobContext], object]
_REGISTRY: dict[str, JobHandler] = {}


class HandlerAlreadyRegistered(Exception):
    pass


class HandlerNotFound(Exception):
    pass


def register_handler(
    job_type: str, handler: JobHandler, *, override: bool = False
) -> None:
    if not job_type:
        raise ValueError("job_type must be non-empty")
    if job_type in _REGISTRY and not override:
        raise HandlerAlreadyRegistered(job_type)
    _REGISTRY[job_type] = handler


def get_handler(job_type: str) -> JobHandler:
    handler = _REGISTRY.get(job_type)
    if handler is None:
        raise HandlerNotFound(job_type)
    return handler


def clear_registry() -> None:
    _REGISTRY.clear()


def registered_types() -> tuple[str, ...]:
    return tuple(sorted(_REGISTRY.keys()))


__all__ = [
    "HandlerAlreadyRegistered",
    "HandlerNotFound",
    "JobHandler",
    "clear_registry",
    "get_handler",
    "register_handler",
    "registered_types",
]
