"""Baseline HTTP security response headers."""
from __future__ import annotations

from typing import Any


class SecurityHeadersMiddleware:
    def __init__(
        self,
        app: Any,
        *,
        hsts: bool = False,
    ) -> None:
        self.app = app
        self.hsts = hsts

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message: dict[str, Any]) -> None:
            if message.get("type") == "http.response.start":
                headers = list(message.get("headers") or [])
                present = {key.lower() for key, _ in headers}

                defaults = [
                    (b"x-content-type-options", b"nosniff"),
                    (b"x-frame-options", b"DENY"),
                    (b"referrer-policy", b"strict-origin-when-cross-origin"),
                    (b"permissions-policy", b"camera=(), microphone=(), geolocation=()"),
                    (b"cross-origin-opener-policy", b"same-origin"),
                ]
                if self.hsts:
                    defaults.append(
                        (
                            b"strict-transport-security",
                            b"max-age=31536000; includeSubDomains",
                        )
                    )

                for key, value in defaults:
                    if key not in present:
                        headers.append((key, value))
                message["headers"] = headers

            await send(message)

        await self.app(scope, receive, send_with_headers)
