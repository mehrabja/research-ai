"""Domain-level job types and state machine.

Framework-independent. No SQLAlchemy, FastAPI, DB, or HTTP imports.
"""
from __future__ import annotations

import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Literal

JobStatus = Literal[
    "queued",
    "processing",
    "retrying",
    "completed",
    "failed",
    "cancelled",
]


ALL_JOB_STATUSES: tuple[str, ...] = (
    "queued",
    "processing",
    "retrying",
    "completed",
    "failed",
    "cancelled",
)


_ALLOWED: dict[str, frozenset[str]] = {
    "queued": frozenset({"processing", "cancelled"}),
    "processing": frozenset({"completed", "retrying", "failed"}),
    "retrying": frozenset({"processing", "cancelled"}),
    "completed": frozenset(),
    "failed": frozenset({"queued"}),
    "cancelled": frozenset(),
}


class InvalidJobTransitionError(ValueError):
    """Raised by ``validate_job_transition`` for illegal transitions."""


def validate_job_transition(
    current_status: str, target_status: str
) -> None:
    allowed = _ALLOWED.get(current_status)
    if allowed is None:
        raise InvalidJobTransitionError(
            f"unknown current status {current_status!r}"
        )
    if target_status not in allowed:
        raise InvalidJobTransitionError(
            f"cannot transition {current_status!r} -> {target_status!r}"
        )


class JobTypes(StrEnum):
    TEST_NOOP = "test_noop"
    EMBEDDING_SOURCE = "embedding_source"
    GENERATE_REPORT = "generate_report"
    DETECT_REPORT = "detect_report"
    HUMANIZE_REPORT = "humanize_report"
    TRANSLATE_REPORT = "translate_report"
    HUMANIZE_POST_TRANSLATION = "humanize_post_translation"

EXECUTABLE_JOB_TYPES: frozenset[str] = frozenset({
    JobTypes.TEST_NOOP,
    JobTypes.EMBEDDING_SOURCE,
    JobTypes.GENERATE_REPORT,
    JobTypes.DETECT_REPORT,
    JobTypes.HUMANIZE_REPORT.value,
    JobTypes.TRANSLATE_REPORT.value,
    JobTypes.HUMANIZE_POST_TRANSLATION.value,
})

RESERVED_JOB_TYPES: frozenset[str] = frozenset()


RETRYABLE_ERROR_CODES: frozenset[str] = frozenset({
    "provider_unavailable",
    "provider_timeout",
    "rate_limited",
    "network_error",
    "connection_reset",
    "deadlock",
    "serialization_failure",
})


def is_retryable(error_code: str) -> bool:
    return error_code in RETRYABLE_ERROR_CODES


@dataclass(frozen=True)
class RetryDecision:
    retry: bool
    error_code: str
    delay_seconds: float | None


@dataclass(frozen=True)
class JobExecutionResult:
    success: bool
    error_code: str | None = None
    error_message: str | None = None


@dataclass(frozen=True)
class JobContext:
    job_id: uuid.UUID
    job_type: str
    attempt_count: int
    worker_id: str
    payload: Mapping[str, Any]


__all__ = [
    "ALL_JOB_STATUSES",
    "EXECUTABLE_JOB_TYPES",
    "InvalidJobTransitionError",
    "JobContext",
    "JobExecutionResult",
    "JobStatus",
    "JobTypes",
    "RESERVED_JOB_TYPES",
    "RETRYABLE_ERROR_CODES",
    "RetryDecision",
    "is_retryable",
    "validate_job_transition",
]
