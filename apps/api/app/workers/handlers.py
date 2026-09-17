"""Built-in handlers.

``test_noop``          — deterministic test handler.
``embedding_source``   — M11 handler that delegates to M9.
``generate_report``    — M12 handler that delegates to the
generation service.
"""
from __future__ import annotations

import logging
import time
import uuid
from typing import cast

from app.core.exceptions import AppError
from app.db.session import SessionLocal
from app.domain.generation import GenerationAlreadySucceeded
from app.domain.jobs import (
    EXECUTABLE_JOB_TYPES,
    RESERVED_JOB_TYPES,
    JobContext,
    JobTypes,
)
from app.services import detection as detection_service
from app.services import embeddings as embeddings_service
from app.services import generation as generation_service
from app.services.detection_profile import (
    build_detection_provider,
    get_current_detection_profile,
)
from app.services.embedding_profile import (
    build_embedding_provider,
    get_current_embedding_profile,
)
from app.services.generation_profile import (
    build_generation_provider,
    get_current_generation_profile,
)
from app.workers.registry import register_handler, registered_types

logger = logging.getLogger(__name__)


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
    from app.db.models.jobs import Job

    job = db.get(Job, job_id)
    if job is None or job.user_id is None:
        raise InvalidEmbeddingPayloadError(
            "embedding job has no owning user"
        )
    return job.user_id


def _embedding_source(ctx: JobContext) -> None:
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

    if result.failed > 0 or result.pending > 0:
        from app.integrations.embeddings.base import (
            EmbeddingProviderUnavailableError,
        )

        raise EmbeddingProviderUnavailableError(
            f"embedding run incomplete: failed={result.failed} "
            f"pending={result.pending}"
        )


# ---------------------------------------------------------------------------
# M12 — generation handler
# ---------------------------------------------------------------------------
class InvalidGenerationPayloadError(AppError):
    code = "INVALID_GENERATION_PAYLOAD"
    status_code = 400
    message = "Generation job payload is invalid."


def _parse_generation_payload(payload: dict) -> uuid.UUID:
    raw = payload.get("report_id")
    if not isinstance(raw, str):
        raise InvalidGenerationPayloadError("report_id is required")
    try:
        return uuid.UUID(raw)
    except (ValueError, TypeError) as exc:
        raise InvalidGenerationPayloadError(
            "report_id must be a valid UUID"
        ) from exc


def _generate_report(ctx: JobContext) -> None:
    from app.db.models.jobs import Job

    report_id = _parse_generation_payload(dict(ctx.payload))

    with SessionLocal() as db:
        job = db.get(Job, ctx.job_id)
        if job is None:
            raise InvalidGenerationPayloadError("job not found")
        if job.job_type != JobTypes.GENERATE_REPORT:
            raise InvalidGenerationPayloadError(
                f"wrong job_type {job.job_type!r}"
            )
        if job.report_id is None or job.report_id != report_id:
            raise InvalidGenerationPayloadError(
                "job.report_id does not match payload.report_id"
            )
        if job.user_id is None:
            raise InvalidGenerationPayloadError(
                "generation job has no owning user"
            )
        user_id = cast(uuid.UUID, job.user_id)

    profile = get_current_generation_profile()
    provider = build_generation_provider(profile)

    try:
        with SessionLocal() as db:
            result = generation_service.generate_report(
                db,
                job_id=ctx.job_id,
                user_id=user_id,
                report_id=report_id,
                provider=provider,
                profile=profile,
            )
    except GenerationAlreadySucceeded:
        logger.info(
            "generate_report_already_succeeded job_id=%s",
            ctx.job_id,
        )
        return

    logger.info(
        "generate_report_done job_id=%s report_id=%s "
        "profile_id=%s cited_markers=%d",
        ctx.job_id,
        report_id,
        result.profile_id,
        len(result.cited_markers),
    )

# ---------------------------------------------------------------------------
# M13 — detection handler
# ---------------------------------------------------------------------------
class InvalidDetectionPayloadError(AppError):
    code = "INVALID_DETECTION_PAYLOAD"
    status_code = 400
    message = "Detection job payload is invalid."


def _parse_detection_payload(
    payload: dict,
) -> tuple[uuid.UUID, uuid.UUID]:
    r = payload.get("report_id")
    v = payload.get("version_id")
    if not isinstance(r, str) or not isinstance(v, str):
        raise InvalidDetectionPayloadError(
            "report_id and version_id are required"
        )
    try:
        return uuid.UUID(r), uuid.UUID(v)
    except (ValueError, TypeError) as exc:
        raise InvalidDetectionPayloadError(
            "ids must be UUIDs"
        ) from exc


def _detect_report(ctx: JobContext) -> None:
    from app.core.exceptions import DetectionAlreadyCompletedError
    from app.db.models.jobs import Job

    report_id, version_id = _parse_detection_payload(
        dict(ctx.payload)
    )

    with SessionLocal() as db:
        job = db.get(Job, ctx.job_id)
        if job is None:
            raise InvalidDetectionPayloadError("job not found")
        if job.job_type != JobTypes.DETECT_REPORT:
            raise InvalidDetectionPayloadError("wrong job_type")
        if job.report_id is None or job.report_id != report_id:
            raise InvalidDetectionPayloadError(
                "job.report_id mismatch"
            )
        if job.user_id is None:
            raise InvalidDetectionPayloadError("no owning user")
        user_id = cast(uuid.UUID, job.user_id)

    profile = get_current_detection_profile()
    provider = build_detection_provider(profile)

    try:
        with SessionLocal() as db:
            result = detection_service.detect_report_version(
                db,
                user_id=user_id,
                report_id=report_id,
                version_id=version_id,
                provider=provider,
                profile=profile,
            )
    except DetectionAlreadyCompletedError:
        logger.info(
            "detect_report_already_completed job_id=%s", ctx.job_id
        )
        return

    logger.info(
        "detect_report_done job_id=%s report_id=%s version_id=%s "
        "label=%s probability=%s",
        ctx.job_id,
        report_id,
        version_id,
        result.label,
        result.probability,
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
    if JobTypes.GENERATE_REPORT not in registered_types():
        register_handler(
            JobTypes.GENERATE_REPORT, _generate_report
        )

    if JobTypes.DETECT_REPORT not in registered_types():
        register_handler(JobTypes.DETECT_REPORT, _detect_report)

__all__ = [
    "EXECUTABLE_JOB_TYPES",
    "InvalidEmbeddingPayloadError",
    "InvalidGenerationPayloadError",
    "RESERVED_JOB_TYPES",
    "InvalidDetectionPayloadError",
    "register_all_handlers",
]
