"""Reusable rate-limit dependencies (M36).

Settings are read at request time via ``setting_name`` so tests can
override them deterministically without capturing config at import.
"""
from __future__ import annotations

from fastapi import Depends, Request

from app.api.dependencies import get_current_user
from app.core.client_ip import get_scope_client_ip
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.db.models.user import User
from app.services.general_rate_limit import get_rate_limit_backend

_WINDOW_SECONDS = 60.0


class RateLimitedAppError(AppError):
    code = "RATE_LIMITED"
    status_code = 429
    message = "Too many requests. Please try again later."

    def __init__(self, *, retry_after: int = 60) -> None:
        super().__init__()
        self.retry_after = max(1, int(retry_after))


def _consume(key: str, limit: int) -> None:
    allowed, retry_after = get_rate_limit_backend().hit(
        key, limit=limit, window_seconds=_WINDOW_SECONDS
    )
    if not allowed:
        raise RateLimitedAppError(retry_after=retry_after)


def enforce_user_rate_limit(category: str, *, setting_name: str):
    def _dep(
        current_user: User = Depends(get_current_user),
    ) -> None:
        limit = int(getattr(get_settings(), setting_name))
        if limit <= 0:
            return
        _consume(f"user:{current_user.id}:{category}", limit)

    return _dep


def enforce_ip_rate_limit(category: str, *, setting_name: str):
    def _dep(request: Request) -> None:
        settings = get_settings()
        limit = int(getattr(settings, setting_name))
        if limit <= 0:
            return
        ip = get_scope_client_ip(
            request.scope,
            trusted_proxies_raw=settings.trusted_proxies,
        )
        _consume(f"ip:{ip}:{category}", limit)

    return _dep


__all__ = [
    "RateLimitedAppError",
    "enforce_ip_rate_limit",
    "enforce_user_rate_limit",
]
