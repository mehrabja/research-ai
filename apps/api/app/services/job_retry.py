"""Retry decisions and backoff calculation."""
from __future__ import annotations

import random
from collections.abc import Callable
from datetime import datetime

from app.core.config import get_settings
from app.domain.jobs import RetryDecision, is_retryable


def compute_backoff(
    *,
    attempt_count: int,
    base_seconds: float,
    max_seconds: float,
    jitter: float,
    rng: Callable[[], float] = random.random,
) -> float:
    """delay = min(max, base * 2^(attempt_count - 1)) + bounded jitter."""
    if attempt_count < 1:
        raise ValueError("attempt_count must be >= 1")
    if base_seconds <= 0:
        raise ValueError("base_seconds must be > 0")
    if max_seconds < base_seconds:
        raise ValueError("max_seconds must be >= base_seconds")
    if not (0.0 <= jitter <= 1.0):
        raise ValueError("jitter must be in [0, 1]")

    raw = base_seconds * (2 ** (attempt_count - 1))
    bounded = min(max_seconds, raw)
    jitter_amount = bounded * jitter * rng()
    return min(max_seconds, bounded + jitter_amount)


def decide_retry(
    *,
    error_code: str,
    attempt_count: int,
    max_attempts: int,
    now: datetime | None = None,
    rng: Callable[[], float] = random.random,
) -> RetryDecision:
    settings = get_settings()
    _ = now

    if attempt_count >= max_attempts:
        return RetryDecision(
            retry=False,
            error_code="max_attempts_exceeded",
            delay_seconds=None,
        )
    if not is_retryable(error_code):
        return RetryDecision(
            retry=False, error_code=error_code, delay_seconds=None
        )
    delay = compute_backoff(
        attempt_count=attempt_count,
        base_seconds=settings.job_retry_base_seconds,
        max_seconds=settings.job_retry_max_seconds,
        jitter=settings.job_retry_jitter,
        rng=rng,
    )
    return RetryDecision(
        retry=True, error_code=error_code, delay_seconds=delay
    )


__all__ = ["compute_backoff", "decide_retry"]
