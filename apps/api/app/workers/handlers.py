"""Built-in handlers.

``test_noop``             — deterministic test handler.
``embedding_source``      — M11 handler that delegates to M9.
``generate_report``       — M12 handler that delegates to the generation service.
``detect_report``         — M13 handler that delegates to the detection service.
``humanize_report``       — M14 handler that delegates to the humanization service.
``translate_report``      — M16 handler that delegates to the translation service.
``humanize_post_translation`` — M17 handler that delegates to the M17 service.
``code_analyze``          — M20 handler for Code Intelligence.
``data_profile``          — M20 handler for Data Intelligence.
``research_classification`` — M21 handler for Research Classification.
"""
from __future__ import annotations

import logging
import time
import uuid
from typing import cast

from sqlalchemy import select

from app.core.exceptions import AppError
from app.db.models.pipeline import TranslationRun, TranslationVersion
from app.db.session import SessionLocal
from app.domain.generation import GenerationAlreadySucceeded
from app.domain.humanization import (
    HumanizationAlreadyCompletedError,
    HumanizationStateError,
)
from app.domain.jobs import (
    EXECUTABLE_JOB_TYPES,
    RESERVED_JOB_TYPES,
    JobContext,
    JobTypes,
)
from app.services import detection as detection_service
from app.services import embeddings as embeddings_service
from app.services import generation as generation_service
from app.services import humanization as humanization_service
from app.services import humanization_jobs
from app.services import jobs as jobs_service
from app.services import post_translation_humanization as m17_service
from app.services import post_translation_humanization_jobs as m17_jobs
from app.services import report_status as report_status_service
from app.services import report_versions as report_versions_service
from app.services import translation as translation_service
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
from app.services.humanization_jobs import (
    HumanizationEnqueueError,
    HumanizationEnqueueStateError,
)
from app.services.humanization_profile import (
    build_policy_from_settings,
    build_post_translation_policy_from_settings,
)
from app.services.translation_profile import (
    build_translation_provider,
    get_current_translation_profile,
)
from app.services.usage import record_humanization_usage
from app.workers.registry import register_handler, registered_types

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# test_noop
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
    code = "INVALID_EMBEDDING_PAYLOAD"
    status_code = 400
    message = "Embedding job payload is invalid."


def _parse_payload(payload: dict) -> tuple[uuid.UUID, uuid.UUID]:
    report_raw = payload.get("report_id")
    source_raw = payload.get("source_id")
    if not isinstance(report_raw, str) or not isinstance(source_raw, str):
        raise InvalidEmbeddingPayloadError(
            "report_id and source_id are required"
        )
    try:
        return uuid.UUID(report_raw), uuid.UUID(source_raw)
    except (ValueError, TypeError) as exc:
        raise InvalidEmbeddingPayloadError(
            "report_id and source_id must be UUIDs"
        ) from exc


def _resolve_owner_user_id(db, job_id: uuid.UUID):
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


def _parse_detection_payload(payload: dict) -> tuple[uuid.UUID, uuid.UUID]:
    r = payload.get("report_id")
    v = payload.get("version_id")
    if not isinstance(r, str) or not isinstance(v, str):
        raise InvalidDetectionPayloadError(
            "report_id and version_id are required"
        )
    try:
        return uuid.UUID(r), uuid.UUID(v)
    except (ValueError, TypeError) as exc:
        raise InvalidDetectionPayloadError("ids must be UUIDs") from exc


def _try_enqueue_humanization_after_detection(
    *,
    user_id: uuid.UUID,
    report_id: uuid.UUID,
    version_id: uuid.UUID,
    policy_version: str | None,
) -> None:
    from app.db.models.pipeline import DetectionRun

    try:
        with SessionLocal() as db:
            det = db.execute(
                select(DetectionRun).where(
                    DetectionRun.report_id == report_id,
                    DetectionRun.version_id == version_id,
                    DetectionRun.status == "completed",
                )
            ).scalar_one_or_none()
            if det is None:
                return

            humanization_jobs.enqueue_humanization_job(
                db=db,
                user_id=user_id,
                report_id=report_id,
                version_id=version_id,
                detection_run_id=det.id,
                jobs_service=jobs_service,
                policy_version=policy_version,
            )
            db.commit()
    except HumanizationEnqueueStateError:
        return
    except HumanizationEnqueueError:
        raise


def _detect_report(ctx: JobContext) -> None:
    from app.core.exceptions import DetectionAlreadyCompletedError
    from app.db.models.jobs import Job

    report_id, version_id = _parse_detection_payload(dict(ctx.payload))

    with SessionLocal() as db:
        job = db.get(Job, ctx.job_id)
        if job is None:
            raise InvalidDetectionPayloadError("job not found")
        if job.job_type != JobTypes.DETECT_REPORT:
            raise InvalidDetectionPayloadError("wrong job_type")
        if job.report_id is None or job.report_id != report_id:
            raise InvalidDetectionPayloadError("job.report_id mismatch")
        if job.user_id is None:
            raise InvalidDetectionPayloadError("no owning user")
        user_id = cast(uuid.UUID, job.user_id)

    profile = get_current_detection_profile()
    provider = build_detection_provider(profile)

    policy_version = (ctx.payload or {}).get("policy_version")

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
        logger.info("detect_report_already_completed job_id=%s", ctx.job_id)
        _try_enqueue_humanization_after_detection(
            user_id=user_id,
            report_id=report_id,
            version_id=version_id,
            policy_version=policy_version,
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

    _try_enqueue_humanization_after_detection(
        user_id=user_id,
        report_id=report_id,
        version_id=version_id,
        policy_version=policy_version,
    )


# ---------------------------------------------------------------------------
# M14 — humanization handler
# ---------------------------------------------------------------------------
class InvalidHumanizationPayloadError(AppError):
    code = "INVALID_HUMANIZATION_PAYLOAD"
    status_code = 400
    message = "Humanization job payload is invalid."


def _parse_humanization_payload(
    payload: dict,
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    r = payload.get("report_id")
    v = payload.get("version_id")
    d = payload.get("detection_run_id")
    if not isinstance(r, str) or not isinstance(v, str) or not isinstance(d, str):
        raise InvalidHumanizationPayloadError(
            "report_id, version_id, and detection_run_id are required"
        )
    try:
        return uuid.UUID(r), uuid.UUID(v), uuid.UUID(d)
    except (ValueError, TypeError) as exc:
        raise InvalidHumanizationPayloadError("ids must be UUIDs") from exc


def _humanize_report(ctx: JobContext) -> None:
    from app.db.models.jobs import Job

    report_id, version_id, detection_run_id = _parse_humanization_payload(
        dict(ctx.payload)
    )

    with SessionLocal() as db:
        job = db.get(Job, ctx.job_id)
        if job is None:
            raise InvalidHumanizationPayloadError("job not found")
        if job.job_type != JobTypes.HUMANIZE_REPORT:
            raise InvalidHumanizationPayloadError(
                f"wrong job_type {job.job_type!r}"
            )
        if job.report_id is None or job.report_id != report_id:
            raise InvalidHumanizationPayloadError(
                "job.report_id does not match payload.report_id"
            )
        if job.user_id is None:
            raise InvalidHumanizationPayloadError(
                "humanization job has no owning user"
            )
        user_id = cast(uuid.UUID, job.user_id)

    policy = build_policy_from_settings(
        version=(ctx.payload or {}).get("policy_version"),
        job_id=str(ctx.job_id),
    )

    gen_profile = get_current_generation_profile()
    provider = build_generation_provider(gen_profile)

    try:
        with SessionLocal() as db:
            result = humanization_service.run_humanization(
                db=db,
                user_id=user_id,
                report_id=report_id,
                version_id=version_id,
                detection_run_id=detection_run_id,
                provider=provider,
                policy=policy,
                usage_recorder=None,
                version_service=report_versions_service,
                status_service=report_status_service,
            )
    except HumanizationAlreadyCompletedError:
        logger.info(
            "humanize_report_already_completed job_id=%s", ctx.job_id
        )
        return
    except HumanizationStateError as exc:
        logger.info(
            "humanize_report_skipped job_id=%s reason=%s",
            ctx.job_id,
            str(exc),
        )
        return

    logger.info(
        "humanize_report_done job_id=%s report_id=%s version_id=%s "
        "status=%s output_version_id=%s",
        ctx.job_id,
        report_id,
        version_id,
        result.status,
        result.output_version_id,
    )


# ---------------------------------------------------------------------------
# M16 — translation handler
# ---------------------------------------------------------------------------
class InvalidTranslationPayloadError(AppError):
    code = "INVALID_TRANSLATION_PAYLOAD"
    status_code = 400
    message = "Translation job payload is invalid."


def _parse_translation_payload(
    payload: dict,
) -> tuple[uuid.UUID, uuid.UUID, str]:
    r = payload.get("report_id")
    v = payload.get("source_version_id")
    t = payload.get("target_language")
    if not isinstance(r, str) or not isinstance(v, str) or not isinstance(t, str):
        raise InvalidTranslationPayloadError(
            "report_id, source_version_id, target_language required"
        )
    try:
        return uuid.UUID(r), uuid.UUID(v), t
    except (ValueError, TypeError) as exc:
        raise InvalidTranslationPayloadError("ids must be UUIDs") from exc


def _enqueue_m17_after_translation(
    *,
    report_id: uuid.UUID,
    user_id: uuid.UUID,
    translation_run_id: uuid.UUID,
    translation_version_id: uuid.UUID,
) -> m17_jobs.EnqueueOutcome:
    """Enqueue M17 after M16 success. Raises on real enqueue failures so
    the calling M16 job retries via the existing queue."""
    policy_version = build_post_translation_policy_from_settings().version
    with SessionLocal() as db:
        result = m17_jobs.enqueue_post_translation_humanization_job(
            db=db,
            user_id=user_id,
            report_id=report_id,
            translation_run_id=translation_run_id,
            translation_version_id=translation_version_id,
            policy_version=policy_version,
        )
        db.commit()
        return result.outcome


def _translate_report(ctx: JobContext) -> None:
    from app.db.models.jobs import Job

    report_id, source_version_id, target_language = _parse_translation_payload(
        dict(ctx.payload)
    )

    with SessionLocal() as db:
        job = db.get(Job, ctx.job_id)
        if job is None:
            raise InvalidTranslationPayloadError("job not found")
        if job.job_type != JobTypes.TRANSLATE_REPORT:
            raise InvalidTranslationPayloadError(
                f"wrong job_type {job.job_type!r}"
            )
        if job.report_id is None or job.report_id != report_id:
            raise InvalidTranslationPayloadError("job.report_id mismatch")
        if job.user_id is None:
            raise InvalidTranslationPayloadError("no owning user")
        user_id = cast(uuid.UUID, job.user_id)

    profile = get_current_translation_profile()
    provider = build_translation_provider(profile)

    try:
        with SessionLocal() as db:
            outcome = translation_service.translate_report(
                db=db,
                user_id=user_id,
                report_id=report_id,
                job_id=ctx.job_id,
                source_version_id=source_version_id,
                target_language=target_language,
                provider=provider,
                profile=profile,
            )
    except translation_service.TranslationAlreadySucceeded as exc:
        logger.info(
            "translate_report_already_succeeded job_id=%s detail=%s",
            ctx.job_id, str(exc),
        )
        # Recovery: resolve exact M16 identities and enqueue M17.
        with SessionLocal() as db:
            trun = db.execute(
                select(TranslationRun).where(
                    TranslationRun.report_id == report_id,
                    TranslationRun.source_version_id == source_version_id,
                    TranslationRun.target_lang == target_language,
                    TranslationRun.status == "success",
                )
            ).scalars().first()
            if trun is None:
                logger.warning(
                    "m16_recovery_no_successful_run report_id=%s", report_id,
                )
                return
            tver = db.execute(
                select(TranslationVersion).where(
                    TranslationVersion.translation_run_id == trun.id,
                )
            ).scalars().first()
            if tver is None:
                logger.warning(
                    "m16_recovery_no_translation_version run_id=%s", trun.id,
                )
                return
            recovered_run_id = trun.id
            recovered_version_id = tver.id

        _enqueue_m17_after_translation(
            report_id=report_id,
            user_id=user_id,
            translation_run_id=recovered_run_id,
            translation_version_id=recovered_version_id,
        )
        return

    logger.info(
        "translate_report_done job_id=%s report_id=%s "
        "src_version=%s target=%s run_id=%s version_id=%s",
        ctx.job_id, report_id, source_version_id, target_language,
        outcome.run_id, outcome.version_id,
    )

    # M16 → M17 handoff (raises on real enqueue failure → M16 retry).
    _enqueue_m17_after_translation(
        report_id=report_id,
        user_id=user_id,
        translation_run_id=outcome.run_id,
        translation_version_id=outcome.version_id,
    )


# ---------------------------------------------------------------------------
# M17 — post-translation humanization handler
# ---------------------------------------------------------------------------
class InvalidPostTranslationHumanizationPayloadError(AppError):
    code = "INVALID_POST_TRANSLATION_HUMANIZATION_PAYLOAD"
    status_code = 400
    message = "Post-translation humanization job payload is invalid."


def _parse_m17_payload(
    payload: dict,
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID, str | None]:
    r = payload.get("report_id")
    tr = payload.get("translation_run_id")
    tv = payload.get("translation_version_id")
    pv = payload.get("policy_version")
    if not isinstance(r, str) or not isinstance(tr, str) or not isinstance(tv, str):
        raise InvalidPostTranslationHumanizationPayloadError(
            "report_id, translation_run_id, translation_version_id required"
        )
    try:
        return (
            uuid.UUID(r),
            uuid.UUID(tr),
            uuid.UUID(tv),
            pv if isinstance(pv, str) else None,
        )
    except (ValueError, TypeError) as exc:
        raise InvalidPostTranslationHumanizationPayloadError(
            "ids must be UUIDs"
        ) from exc


def _humanize_post_translation(ctx: JobContext) -> None:
    from app.db.models.jobs import Job

    report_id, translation_run_id, translation_version_id, policy_version = (
        _parse_m17_payload(dict(ctx.payload))
    )

    with SessionLocal() as db:
        job = db.get(Job, ctx.job_id)
        if job is None:
            raise InvalidPostTranslationHumanizationPayloadError("job not found")
        if job.job_type != JobTypes.HUMANIZE_POST_TRANSLATION.value:
            raise InvalidPostTranslationHumanizationPayloadError(
                f"wrong job_type {job.job_type!r}"
            )
        if job.report_id is None or job.report_id != report_id:
            raise InvalidPostTranslationHumanizationPayloadError(
                "job.report_id mismatch"
            )
        if job.user_id is None:
            raise InvalidPostTranslationHumanizationPayloadError(
                "no owning user"
            )
        user_id = cast(uuid.UUID, job.user_id)

    policy = build_post_translation_policy_from_settings(
        job_id=str(ctx.job_id),
        version=policy_version,
    )
    gen_provider = build_generation_provider(get_current_generation_profile())
    det_profile = get_current_detection_profile()
    det_provider = build_detection_provider(det_profile)

    try:
        with SessionLocal() as db:
            outcome = m17_service.run_post_translation_humanization(
                db=db,
                user_id=user_id,
                report_id=report_id,
                translation_run_id=translation_run_id,
                translation_version_id=translation_version_id,
                provider=gen_provider,
                detection_provider=det_provider,
                detection_profile=det_profile,
                policy=policy,
                version_service=report_versions_service,
                usage_recorder=record_humanization_usage,
            )
    except m17_service.PostTranslationHumanizationAlreadyCompleted as exc:
        logger.info(
            "humanize_post_translation_already_completed job_id=%s detail=%s",
            ctx.job_id, str(exc),
        )
        return

    logger.info(
        "humanize_post_translation_done job_id=%s report_id=%s "
        "translated_version_id=%s output_version_id=%s status=%s",
        ctx.job_id, report_id,
        outcome.translated_version_id, outcome.output_version_id, outcome.status,
    )


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# M39 — email delivery
# ---------------------------------------------------------------------------
class InvalidEmailPayloadError(AppError):
    code = "INVALID_EMAIL_PAYLOAD"
    status_code = 400
    message = "Email job payload is invalid."


def _email_user_id(ctx: JobContext) -> uuid.UUID:
    raw = (ctx.payload or {}).get("user_id")
    if not isinstance(raw, str):
        raise InvalidEmailPayloadError("user_id is required")
    try:
        return uuid.UUID(raw)
    except (ValueError, TypeError) as exc:
        raise InvalidEmailPayloadError("user_id must be a UUID") from exc


def _frontend_link(path: str, token: str) -> str:
    settings = get_settings()
    base = settings.frontend_base_url.rstrip("/")
    if not base:
        raise AppError(
            "FRONTEND_BASE_URL must be configured for email delivery."
        )
    from urllib.parse import quote

    return f"{base}/{path}?token={quote(token, safe='')}"


def _send_email_verification(ctx: JobContext) -> None:
    from app.db.models.user import User
    from app.services.auth_tokens import issue_email_verification_token
    from app.services.email_provider import build_email_provider
    from app.integrations.email import EmailMessagePayload

    user_id = _email_user_id(ctx)
    with SessionLocal() as db:
        user = db.get(User, user_id)
        if user is None or not user.is_active or user.email_verified_at is not None:
            return
        token = issue_email_verification_token(db, user_id=user_id)
        link = _frontend_link("verify-email", token)
        provider = build_email_provider()
        provider.send(
            EmailMessagePayload(
                to=user.email,
                subject="Verify your Research AI email",
                text=(
                    "Verify your email address by opening this link:\n"
                    f"{link}\n"
                    "This link expires according to the account security policy."
                ),
            )
        )
        db.commit()


def _send_password_reset(ctx: JobContext) -> None:
    from app.db.models.user import User
    from app.services.auth_tokens import issue_password_reset_token
    from app.services.email_provider import build_email_provider
    from app.integrations.email import EmailMessagePayload

    user_id = _email_user_id(ctx)
    with SessionLocal() as db:
        user = db.get(User, user_id)
        if user is None or not user.is_active:
            return
        token = issue_password_reset_token(db, user_id=user_id)
        link = _frontend_link("reset-password", token)
        provider = build_email_provider()
        provider.send(
            EmailMessagePayload(
                to=user.email,
                subject="Reset your Research AI password",
                text=(
                    "Reset your password by opening this link:\n"
                    f"{link}\n"
                    "If you did not request this, you can ignore this email."
                ),
            )
        )
        db.commit()


def register_all_handlers() -> None:

    if JobTypes.TEST_NOOP not in registered_types():
        register_handler(JobTypes.TEST_NOOP, _test_noop)

    if JobTypes.EMBEDDING_SOURCE not in registered_types():
        register_handler(JobTypes.EMBEDDING_SOURCE, _embedding_source)

    if JobTypes.GENERATE_REPORT not in registered_types():
        register_handler(JobTypes.GENERATE_REPORT, _generate_report)

    if JobTypes.DETECT_REPORT not in registered_types():
        register_handler(JobTypes.DETECT_REPORT, _detect_report)

    if JobTypes.HUMANIZE_REPORT not in registered_types():
        register_handler(JobTypes.HUMANIZE_REPORT, _humanize_report)

    if JobTypes.TRANSLATE_REPORT not in registered_types():
        register_handler(JobTypes.TRANSLATE_REPORT, _translate_report)

    if JobTypes.HUMANIZE_POST_TRANSLATION not in registered_types():
        register_handler(
            JobTypes.HUMANIZE_POST_TRANSLATION, _humanize_post_translation
        )

    if JobTypes.SEND_EMAIL_VERIFICATION not in registered_types():
        register_handler(JobTypes.SEND_EMAIL_VERIFICATION, _send_email_verification)
    if JobTypes.SEND_PASSWORD_RESET not in registered_types():
        register_handler(JobTypes.SEND_PASSWORD_RESET, _send_password_reset)

    from app.workers.intelligence_handlers import (
        handle_code_analyze,
        handle_data_profile,
    )
    if "code_analyze" not in registered_types():
        register_handler("code_analyze", handle_code_analyze)
    if "data_profile" not in registered_types():
        register_handler("data_profile", handle_data_profile)

    from app.workers.classification_handlers import (
        handle_research_classification,
    )
    if "research_classification" not in registered_types():
        register_handler(
            "research_classification", handle_research_classification
        )

    from app.workers.literature_handlers import (
        handle_literature_analyze,
    )
    if "literature_analyze" not in registered_types():
        register_handler(
            "literature_analyze", handle_literature_analyze
        )

__all__ = [
    "EXECUTABLE_JOB_TYPES",
    "InvalidEmbeddingPayloadError",
    "InvalidGenerationPayloadError",
    "InvalidDetectionPayloadError",
    "InvalidHumanizationPayloadError",
    "InvalidTranslationPayloadError",
    "InvalidPostTranslationHumanizationPayloadError",
    "RESERVED_JOB_TYPES",
    "register_all_handlers",
]
