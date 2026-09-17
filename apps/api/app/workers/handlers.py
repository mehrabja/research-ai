"""Built-in handlers.

``test_noop``          — deterministic test handler.
``embedding_source``   — M11 handler that delegates to the M9
embedding service. No provider logic lives here.
"""
from __future__ import annotations

import logging
import time
import uuid

from app.core.exceptions import AppError
from app.db.session import SessionLocal
from app.domain.jobs import (
    EXECUTABLE_JOB_TYPES,
    RESERVED_JOB_TYPES,
    JobContext,
    JobTypes,
)
from app.services import embeddings as embeddings_service
from app.services.embedding_profile import (
    build_embedding_provider,
    get_current_embedding_profile,
)
from app.workers.registry import register_handler, registered_types

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Test handler
# ---------------------------------------------------------------------------
def _test_noop(ctx: JobContext) -> None:
    mode = (ctx.payload or {}).get("mode", "success")
    if mode == "success":
        return
    if mode == "retryable":
        raise TimeoutError("simulated retryable failure")
    if mode == "permanent":
        raise ValueError("simulated permanent failure")
    if mode == "sleep":
        seconds = float((ctx.payload or {}).get("seconds", 1.0))
        time.sleep(max(0.0, min(seconds, 10.0)))
        return
    raise ValueError(f"unknown mode: {mode!r}")


# ---------------------------------------------------------------------------
# M11 — embedding handler
# ---------------------------------------------------------------------------
class InvalidEmbeddingPayloadError(AppError):
    """Permanent failure: payload does not match the contract."""

    code = "INVALID_EMBEDDING_PAYLOAD"
    status_code = 400
    message = "Embedding job payload is invalid."


def _parse_payload(payload: dict) -> tuple[uuid.UUID, uuid.UUID]:
    report_raw = payload.get("report_id")
    source_raw = payload.get("source_id")
    if not isinstance(report_raw, str) or not isinstance(
        source_raw, str
    ):
        raise InvalidEmbeddingPayloadError(
            "report_id and source_id are required"
        )
    try:
        return uuid.UUID(report_raw), uuid.UUID(source_raw)
    except (ValueError, TypeError) as exc:
        raise InvalidEmbeddingPayloadError(
            "report_id and source_id must be UUIDs"
        ) from exc


def _resolve_owner_user_id(  # noqa: ANN001
    db, job_id: uuid.UUID
):  # noqa: ANN202
    """Read the job's owner user_id."""
    from app.db.models.jobs import Job

    job = db.get(Job, job_id)
    if job is None or job.user_id is None:
        raise InvalidEmbeddingPayloadError(
            "embedding job has no owning user"
        )
    return job.user_id


def _embedding_source(ctx: JobContext) -> None:
    """M11 handler. Delegates embedding to the M9 service."""
    report_id, source_id = _parse_payload(dict(ctx.payload))

    profile = get_current_embedding_profile()
    provider = build_embedding_provider(profile)

    with SessionLocal() as db:
        user_id = _resolve_owner_user_id(db, ctx.job_id)

    with SessionLocal() as db:
        result = embeddings_service.embed_source(
            db,
            user_id=user_id,
            report_id=report_id,
            source_id=source_id,
            provider=provider,
            profile=profile,
        )

    logger.info(
        "embedding_source_done job_id=%s report_id=%s source_id=%s "
        "total=%d embedded=%d already_current=%d failed=%d pending=%d",
        ctx.job_id,
        report_id,
        source_id,
        result.total_chunks,
        result.embedded,
        result.already_current,
        result.failed,
        result.pending,
    )

    # Partial-result policy: M9 may return normally while some chunks
    # were not embedded. Treat an incomplete run as a retryable
    # failure so M10 retries; M9 idempotency guarantees the next
    # attempt skips current chunks.
    if result.failed > 0 or result.pending > 0:
        from app.integrations.embeddings.base import (
            EmbeddingProviderUnavailableError,
        )

        raise EmbeddingProviderUnavailableError(
            f"embedding run incomplete: failed={result.failed} "
            f"pending={result.pending}"
        )


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------
def register_all_handlers() -> None:
    if JobTypes.TEST_NOOP not in registered_types():
        register_handler(JobTypes.TEST_NOOP, _test_noop)
    if JobTypes.EMBEDDING_SOURCE not in registered_types():
        register_handler(
            JobTypes.EMBEDDING_SOURCE, _embedding_source
        )


__all__ = [
    "EXECUTABLE_JOB_TYPES",
    "InvalidEmbeddingPayloadError",
    "RESERVED_JOB_TYPES",
    "register_all_handlers",
]
