"""Per-IP global rate limit middleware (M36).

* X-Request-ID is NOT emitted here (owned by RequestIdMiddleware).
* OPTIONS bypasses the limiter (CORS preflight).
* limit_per_minute == 0 disables; < 0 is rejected at construction.
"""
from __future__ import annotations

import json
from typing import Any

from app.core.client_ip import get_scope_client_ip
from app.core.request_context import get_request_id
from app.services.general_rate_limit import (
    RateLimitBackend,
    get_rate_limit_backend,
)

_WINDOW_SECONDS = 60.0


def _json_429(retry_after: int) -> bytes:
    err: dict[str, Any] = {
        "code": "RATE_LIMITED",
        "message": "Too many requests. Please try again later.",
        "retry_after": int(retry_after),
    }
    rid = get_request_id()
    if rid:
        err["request_id"] = rid
    return json.dumps({"error": err}).encode("utf-8")


class GlobalRateLimitMiddleware:
    def __init__(
        self,
        app: Any,
        *,
        limit_per_minute: int,
        trusted_proxies_raw: str = "",
        backend: RateLimitBackend | None = None,
    ) -> None:
        if (
            not isinstance(limit_per_minute, int)
            or isinstance(limit_per_minute, bool)
            or limit_per_minute < 0
        ):
            raise ValueError(
                "limit_per_minute must be an integer >= 0"
            )
        self.app = app
        self.limit = limit_per_minute
        self._trusted_proxies_raw = trusted_proxies_raw
        self._backend = backend

    def _resolve_backend(self) -> RateLimitBackend:
        return self._backend or get_rate_limit_backend()

    async def __call__(
        self, scope: dict[str, Any], receive: Any, send: Any
    ) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        if (scope.get("method") or "").upper() == "OPTIONS":
            await self.app(scope, receive, send)
            return
        if self.limit <= 0:
            await self.app(scope, receive, send)
            return

        ip = get_scope_client_ip(
            scope, trusted_proxies_raw=self._trusted_proxies_raw
        )
        allowed, retry_after = self._resolve_backend().hit(
            f"ip:{ip}",
            limit=self.limit,
            window_seconds=_WINDOW_SECONDS,
        )
        if not allowed:
            await self._reject(send, retry_after)
            return
        await self.app(scope, receive, send)

    async def _reject(self, send: Any, retry_after: int) -> None:
        payload = _json_429(retry_after)
        headers = [
            (b"content-type", b"application/json"),
            (b"content-length", str(len(payload)).encode("latin-1")),
            (b"retry-after", str(int(retry_after)).encode("latin-1")),
        ]
        await send({
            "type": "http.response.start",
            "status": 429,
            "headers": headers,
        })
        await send({"type": "http.response.body", "body": payload})


__all__ = ["GlobalRateLimitMiddleware"]
