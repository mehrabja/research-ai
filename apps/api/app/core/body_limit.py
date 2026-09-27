"""Request body size enforcement (M36).

* Applies to all HTTP methods.
* Content-Length must be a strict decimal digit string: ``[0-9]+``
  matched with ``fullmatch``. No whitespace trimming, no signs.
* Duplicate Content-Length headers must be byte-identical; otherwise
  the request is rejected with 400.
* The middleware buffers the request body up to ``max_bytes`` BEFORE
  invoking downstream. If the body exceeds the limit, a 413 is
  emitted and the downstream app is never called.
* Does NOT emit X-Request-ID (owned by RequestIdMiddleware).

Trade-off: for streaming/chunked bodies the middleware buffers the
entire payload in memory, bounded by ``max_bytes`` (default 10 MiB).
This is the price of guaranteeing that an oversized request cannot
start endpoint execution. True streaming without buffering cannot
provide that guarantee, because FastAPI/Starlette invokes the
endpoint coroutine before the body has been fully read.
"""
from __future__ import annotations

import json
import re
from typing import Any

from app.core.request_context import get_request_id

_MAX_SANE_CONTENT_LENGTH = 10 * 1024 * 1024 * 1024  # 10 GiB
_DIGITS_RE = re.compile(r"[0-9]+")


class RequestBodyTooLarge(Exception):
    """Retained for API compatibility; not raised by the new design."""

    def __init__(self, max_bytes: int, observed: int) -> None:
        super().__init__(
            f"body exceeded {max_bytes} bytes (observed {observed})"
        )
        self.max_bytes = max_bytes
        self.observed = observed


def _collect_content_lengths(scope: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for key, value in scope.get("headers") or []:
        if key == b"content-length":
            try:
                values.append(value.decode("latin-1"))
            except UnicodeDecodeError:
                values.append("\ufffd")
    return values


def _parse_declared_length(scope: dict[str, Any]) -> int | None:
    raw_values = _collect_content_lengths(scope)
    if not raw_values:
        return None

    first = raw_values[0]
    if _DIGITS_RE.fullmatch(first) is None:
        raise ValueError("malformed Content-Length")
    for v in raw_values[1:]:
        if v != first:
            raise ValueError("conflicting Content-Length")

    try:
        length = int(first, 10)
    except ValueError as exc:
        raise ValueError("malformed Content-Length") from exc

    if length > _MAX_SANE_CONTENT_LENGTH:
        raise ValueError("unreasonable Content-Length")
    return length


def _error_body(
    code: str, message: str, *, extra: dict[str, Any] | None = None
) -> bytes:
    err: dict[str, Any] = {"code": code, "message": message}
    rid = get_request_id()
    if rid:
        err["request_id"] = rid
    if extra:
        err.update(extra)
    return json.dumps({"error": err}).encode("utf-8")


class BodyLimitMiddleware:
    def __init__(self, app: Any, *, max_bytes: int) -> None:
        if (
            not isinstance(max_bytes, int)
            or isinstance(max_bytes, bool)
            or max_bytes < 1
        ):
            raise ValueError("max_bytes must be an integer >= 1")
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(
        self, scope: dict[str, Any], receive: Any, send: Any
    ) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        # File uploads are streamed and size-checked by the upload service;
        # buffering them here would defeat large-file support and duplicate
        # the authoritative document_max_bytes policy.
        settings = None
        try:
            from app.core.config import get_settings
            settings = get_settings()
        except Exception:
            settings = None
        path = str(scope.get("path") or "")
        method = str(scope.get("method") or "").upper()
        if (
            settings is not None
            and settings.body_limit_stream_uploads
            and method == "POST"
            and path.endswith(settings.body_limit_stream_upload_suffix)
        ):
            await self.app(scope, receive, send)
            return

        try:
            declared = _parse_declared_length(scope)
        except ValueError:
            await self._send(
                send,
                status=400,
                body=_error_body(
                    "INVALID_CONTENT_LENGTH",
                    "Content-Length header is invalid.",
                ),
            )
            return

        if declared is not None and declared > self.max_bytes:
            await self._send_413(send, declared)
            return

        # Buffer the body up to max_bytes. If overflow, reject without
        # invoking downstream so endpoint execution never begins.
        body_parts: list[bytes] = []
        total = 0
        disconnected = False
        while True:
            message = await receive()
            mtype = message.get("type")
            if mtype == "http.disconnect":
                disconnected = True
                break
            if mtype != "http.request":
                continue
            chunk = message.get("body") or b""
            total += len(chunk)
            if total > self.max_bytes:
                await self._send_413(send, total)
                return
            body_parts.append(chunk)
            if not message.get("more_body"):
                break

        if disconnected:
            # Client went away before body completed; nothing to send.
            return

        buffered = b"".join(body_parts)
        replayed = False

        async def receive_wrapper() -> dict[str, Any]:
            nonlocal replayed
            if not replayed:
                replayed = True
                return {
                    "type": "http.request",
                    "body": buffered,
                    "more_body": False,
                }
            # Delegate to the real receive for subsequent calls so
            # StreamingResponse's listen_for_disconnect waits for a
            # genuine client disconnect instead of firing immediately.
            return await receive()

        await self.app(scope, receive_wrapper, send)

    async def _send_413(self, send: Any, observed: int) -> None:
        await self._send(
            send,
            status=413,
            body=_error_body(
                "REQUEST_TOO_LARGE",
                "Request body exceeds the maximum allowed size.",
                extra={
                    "max_bytes": self.max_bytes,
                    "observed_bytes": observed,
                },
            ),
        )

    async def _send(
        self, send: Any, *, status: int, body: bytes
    ) -> None:
        headers = [
            (b"content-type", b"application/json"),
            (b"content-length", str(len(body)).encode("latin-1")),
        ]
        await send({
            "type": "http.response.start",
            "status": status,
            "headers": headers,
        })
        await send({"type": "http.response.body", "body": body})


__all__ = ["BodyLimitMiddleware", "RequestBodyTooLarge"]
