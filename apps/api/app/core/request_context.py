"""Request correlation context (M36).

A request ID is a *correlation* identifier only. It is never:
  * a user identity
  * an authorization decision
  * a deterministic content/context hash input
  * a job/run identity

It lives in a ``contextvars.ContextVar`` so that synchronous and
asynchronous code paths (including FastAPI exception handlers and
logging filters) can read it uniformly.
"""
from __future__ import annotations

import contextvars
import logging
import re
import time
import uuid
from typing import Any, Final

_REQUEST_ID_RE: Final = re.compile(r"^[A-Za-z0-9._:\-]{1,128}$")

_current: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "current_request_id", default=None
)

logger = logging.getLogger(__name__)


def generate_request_id() -> str:
    return uuid.uuid4().hex


def sanitize_request_id(candidate: str | None) -> str | None:
    """Return a safe request ID or ``None``.

    Accepts only a conservative character set and bounded length. Any
    incoming header that does not match is treated as if it were absent.
    """
    if not candidate:
        return None
    candidate = candidate.strip()
    if not candidate or not _REQUEST_ID_RE.match(candidate):
        return None
    return candidate


def set_request_id(request_id: str) -> contextvars.Token[str | None]:
    return _current.set(request_id)


def get_request_id() -> str | None:
    return _current.get()


def reset_request_id(token: contextvars.Token[str | None]) -> None:
    _current.reset(token)


class RequestIdMiddleware:
    """Pure-ASGI middleware that attaches a correlation ID.

    Behaviour:
      * Validates any incoming request-ID header. Invalid values are
        ignored and replaced.
      * Sets the ID in the request scope (``scope["state"]``) and in a
        contextvar before calling downstream.
      * Guarantees EXACTLY ONE canonical response header. Any existing
        matching headers produced downstream are removed first.
      * Resets the contextvar in a ``finally`` block.
    """

    def __init__(
        self,
        app: Any,
        *,
        header_name: str = "X-Request-ID",
        accept_incoming: bool = True,
    ) -> None:
        self.app = app
        self.header_name = header_name
        self._header_bytes = header_name.lower().encode("latin-1")
        self.accept_incoming = accept_incoming

    async def __call__(
        self,
        scope: dict[str, Any],
        receive: Any,
        send: Any,
    ) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        incoming: str | None = None
        if self.accept_incoming:
            for key, value in scope.get("headers") or []:
                if key == self._header_bytes:
                    try:
                        incoming = value.decode("latin-1")
                    except UnicodeDecodeError:
                        incoming = None
                    break

        request_id = (
            sanitize_request_id(incoming) or generate_request_id()
        )

        state = scope.get("state")
        if isinstance(state, dict):
            state["request_id"] = request_id

        header_pair = (
            self._header_bytes,
            request_id.encode("latin-1"),
        )
        started_at = time.monotonic()
        response_status = 500

        async def send_wrapper(message: dict[str, Any]) -> None:
            nonlocal response_status
            if message["type"] == "http.response.start":
                response_status = int(message.get("status", 500))
                headers = [
                    (k, v)
                    for (k, v) in (message.get("headers") or [])
                    if k != self._header_bytes
                ]
                headers.append(header_pair)
                message["headers"] = headers
            await send(message)

        token = set_request_id(request_id)
        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration_ms = round((time.monotonic() - started_at) * 1000, 2)
            logger.info(
                "request_complete method=%s path=%s status=%s duration_ms=%s",
                scope.get("method", ""),
                scope.get("path", ""),
                response_status,
                duration_ms,
                extra={"event": "request_complete"},
            )
            reset_request_id(token)


__all__ = [
    "RequestIdMiddleware",
    "generate_request_id",
    "get_request_id",
    "reset_request_id",
    "sanitize_request_id",
    "set_request_id",
]
