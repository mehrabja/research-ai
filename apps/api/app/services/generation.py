"""Generation orchestration with durable at-least-once attempt lifecycle."""
from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import (
    InvalidJobStateError,
    NoEvidenceAvailableError,
)
from app.db.models.pipeline import GenerationRun
from app.db.models.project import Project
from app.db.models.report import Report
from app.domain.generation import (
    AttemptState,
    EmptyGenerationError,
    GenerationAlreadySucceeded,
    GenerationAttemptLease,
    GenerationContext,
    GenerationProfile,
    GenerationProviderResult,
    GenerationResult,
    UnknownEvidenceMarkerError,
    build_generation_profile_id,
    validate_generation_output,
)
from app.integrations.generation.base import (
    GenerationAuthenticationError,
    GenerationInputTooLargeError,
    GenerationInvalidRequestError,
    GenerationInvalidResponseError,
    GenerationProvider,
    GenerationProviderUnavailableError,
    GenerationRateLimitError,
    GenerationTimeoutError,
)
from app.services import report_status as report_status_service
from app.services import report_versions as report_versions_service
from app.services import retrieval as retrieval_service
from app.services.embedding_profile import (
    build_embedding_provider,
    get_current_embedding_profile,
)
from app.services.generation_profile import (
    get_current_generation_profile,
)
from app.services.usage_contract import ProviderUsage, record_provider_usage
from app.services.generation_prompt import (
    build_evidence_set,
    build_system_prompt,
    build_user_prompt,
)

logger = logging.getLogger(__name__)

_GENERATING = "generating"
_REVIEW_1 = "review_1"
_FAILED = "failed"

_PERMANENT_GENERATION_ERRORS: tuple[type[BaseException], ...] = (
    GenerationAuthenticationError,
    GenerationInvalidRequestError,
    GenerationInvalidResponseError,
    GenerationInputTooLargeError,
    EmptyGenerationError,
    UnknownEvidenceMarkerError,
    NoEvidenceAvailableError,
)

_RETRYABLE_GENERATION_ERRORS: tuple[type[BaseException], ...] = (
    GenerationRateLimitError,
    GenerationTimeoutError,
    GenerationProviderUnavailableError,
)


def _is_permanent_generation_error(exc: BaseException) -> bool:
    return isinstance(exc, _PERMANENT_GENERATION_ERRORS)


def _is_retryable_generation_error(exc: BaseException) -> bool:
    return isinstance(exc, _RETRYABLE_GENERATION_ERRORS)


def _error_code_for(exc: BaseException) -> str:
    if isinstance(exc, GenerationAuthenticationError):
        return "authentication_error"
    if isinstance(exc, GenerationInvalidRequestError):
        return "invalid_payload"
    if isinstance(exc, GenerationInvalidResponseError):
        return "invalid_provider_response"
    if isinstance(exc, GenerationInputTooLargeError):
        return "input_too_large"
    if isinstance(exc, EmptyGenerationError):
        return "empty_generation"
    if isinstance(exc, UnknownEvidenceMarkerError):
        return "unknown_evidence_marker"
    if isinstance(exc, NoEvidenceAvailableError):
        return "no_evidence"
    if isinstance(exc, InvalidJobStateError):
        return "invalid_state"
    return "permanent_generation_error"


def _acquire_or_create_attempt(
    db: Session,
    *,
    job_id: uuid.UUID,
    user_id: uuid.UUID,
    report_id: uuid.UUID,
    profile_id: str,
) -> GenerationAttemptLease:
    report = db.execute(
        select(Report)
        .where(
            Report.id == report_id,
            Report.user_id == user_id,
            Report.deleted_at.is_(None),
        )
        .with_for_update()
    ).scalar_one_or_none()
    if report is None:
        from app.core.exceptions import ReportNotFound
        raise ReportNotFound()

    # 1. Existing attempt for THIS job_id → short-circuit.
    #    Checked BEFORE the lifecycle transition so a duplicate
    #    delivery of the same job sees already_succeeded even if
    #    the report has already advanced to review_1.
    candidates = list(
        db.execute(
            select(GenerationRun).where(
                GenerationRun.report_id == report_id
            )
        ).scalars().all()
    )
    for run in candidates:
        oj = run.output_json or {}
        if str(oj.get("job_id")) != str(job_id):
            continue
        if run.status == "success":
            return GenerationAttemptLease(
                run=run, state="already_succeeded"
            )
        if run.status == "running":
            return GenerationAttemptLease(
                run=run, state="existing_running"
            )

    # 2. No existing attempt → lifecycle transition.
    if report.status == "draft":
        report_status_service.update_report_status(
            db,
            user_id=user_id,
            report_id=report_id,
            new_status=_GENERATING,
            commit=False,
        )
    elif report.status == _GENERATING:
        pass
    else:
        raise InvalidJobStateError(
            f"cannot generate from status {report.status!r}"
        )

    # 3. Create new attempt.
    run = GenerationRun(
        report_id=report_id,
        prompt_version=profile_id,
        model_provider=None,
        model_version=None,
        input_token_count=None,
        output_token_count=None,
        output_json={
            "job_id": str(job_id),
            "attempt_status": "running",
            "profile_id": profile_id,
        },
        status="running",
    )
    db.add(run)
    db.flush()
    return GenerationAttemptLease(run=run, state="created")


def generate_report(
    db: Session,
    *,
    job_id: uuid.UUID,
    user_id: uuid.UUID,
    report_id: uuid.UUID,
    provider: GenerationProvider,
    profile: GenerationProfile | None = None,
) -> GenerationResult:
    profile = profile or get_current_generation_profile()
    profile_id = build_generation_profile_id(profile)
    settings = get_settings()

    try:
        lease = _acquire_or_create_attempt(
            db,
            job_id=job_id,
            user_id=user_id,
            report_id=report_id,
            profile_id=profile_id,
        )
        db.commit()
        attempt_run = cast(Any, lease.run)
        attempt_id = cast(uuid.UUID, attempt_run.id)
        state: AttemptState = lease.state
    except Exception:
        db.rollback()
        raise

    if state == "already_succeeded":
        raise GenerationAlreadySucceeded()

    report = _load_report(db, user_id, report_id)
    embedding_profile = get_current_embedding_profile()
    embedding_provider = build_embedding_provider(embedding_profile)
    retrieved, _coverage = retrieval_service.retrieve(
        db,
        user_id=user_id,
        report_id=report_id,
        query=report.topic,
        top_k=settings.generation_max_context_chunks,
        mode="hybrid",
        algorithm="ann",
        source_ids=None,
        provider=embedding_provider,
        profile=embedding_profile,
    )
    evidence = build_evidence_set(
        retrieved, max_items=settings.generation_max_context_chunks
    )

    if not evidence.items:
        _fail_attempt_and_report(
            db,
            attempt_id=attempt_id,
            user_id=user_id,
            report_id=report_id,
            error_code="no_evidence",
        )
        raise NoEvidenceAvailableError()

    system_prompt = build_system_prompt()
    user_prompt = build_user_prompt(
        topic=report.topic,
        output_language=report.output_language,
        domain=report.domain,
        audience_level=report.audience_level,
        tone=report.tone,
        length=report.length,
        structure_template=report.structure_template,
        evidence=evidence,
    )
    context = GenerationContext(
        report_id=report_id,
        job_id=job_id,
        topic=report.topic,
        output_language=report.output_language,
        domain=report.domain,
        audience_level=report.audience_level,
        tone=report.tone,
        length=report.length,
        structure_template=report.structure_template,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        evidence=evidence,
        profile=profile,
    )

    try:
        provider_result: GenerationProviderResult = provider.generate(
            system_prompt=context.system_prompt,
            user_prompt=context.user_prompt,
            temperature=profile.temperature,
            max_output_tokens=profile.max_output_tokens,
        )
        cited = validate_generation_output(
            text=provider_result.text, evidence=evidence
        )
    except BaseException as exc:
        if _is_permanent_generation_error(exc):
            _fail_attempt_and_report(
                db,
                attempt_id=attempt_id,
                user_id=user_id,
                report_id=report_id,
                error_code=_error_code_for(exc),
            )
        raise

    try:
        _persist_success_atomic(
            db,
            attempt_id=attempt_id,
            job_id=job_id,
            user_id=user_id,
            report_id=report_id,
            context=context,
            provider_result=provider_result,
            cited=cited,
            profile_id=profile_id,
        )
    except GenerationAlreadySucceeded:
        raise
    except Exception:
        db.rollback()
        raise

    return GenerationResult(
        text=provider_result.text,
        language=report.output_language,
        profile_id=profile_id,
        evidence=evidence,
        cited_markers=cited,
        provider_result=provider_result,
    )


def _persist_success_atomic(
    db: Session,
    *,
    attempt_id: uuid.UUID,
    job_id: uuid.UUID,
    user_id: uuid.UUID,
    report_id: uuid.UUID,
    context: GenerationContext,
    provider_result: GenerationProviderResult,
    cited: tuple[str, ...],
    profile_id: str,
) -> None:
    marker_map = context.evidence.marker_map()
    claims_evidence = [
        {
            "marker": m,
            "evidence_id": marker_map[m].evidence_id,
            "source_id": str(marker_map[m].source_id),
            "chunk_id": str(marker_map[m].chunk_id),
        }
        for m in cited
    ]
    output_json = {
        "job_id": str(job_id),
        "attempt_status": "success",
        "profile_id": profile_id,
        "text": provider_result.text,
        "language": context.output_language,
        "evidence": [
            {
                "marker": it.marker,
                "rank": it.rank,
                "evidence_id": it.evidence_id,
                "source_id": str(it.source_id),
                "chunk_id": str(it.chunk_id),
                "fusion_score": it.fusion_score,
            }
            for it in context.evidence.items
        ],
        "cited_markers": list(cited),
        "claims_evidence": claims_evidence,
    }

    try:
        updated_id = db.execute(
            update(GenerationRun)
            .where(
                GenerationRun.id == attempt_id,
                GenerationRun.status == "running",
            )
            .values(
                status="success",
                model_provider=provider_result.provider,
                model_version=provider_result.model,
                input_token_count=provider_result.input_tokens,
                output_token_count=provider_result.output_tokens,
                output_json=output_json,
                completed_at=datetime.now(UTC),
            )
            .returning(GenerationRun.id)
        ).scalar_one_or_none()
        if updated_id is None:
            db.rollback()
            raise GenerationAlreadySucceeded()

        report_versions_service.create_report_version(
            db,
            user_id=user_id,
            report_id=report_id,
            language=context.output_language,
            content=provider_result.text,
            change_type="generated",
            commit=False,
        )

        project = db.get(Project, report.project_id)
        if project is None:
            raise InvalidJobStateError("report project not found")
        total_tokens = (provider_result.total_tokens or 0)
        record_provider_usage(
            db,
            workspace_id=project.workspace_id,
            user_id=user_id,
            source_id=None,
            usage=ProviderUsage(
                capability="generation",
                operation="report_generation",
                provider=provider_result.provider,
                model=provider_result.model,
                input_tokens=provider_result.input_tokens or 0,
                output_tokens=provider_result.output_tokens or 0,
                units=max(1, total_tokens),
                request_id=getattr(provider_result, "request_id", None),
                metadata={"report_id": str(report_id)},
            ),
            idempotency_key=f"generation:{attempt_id}:provider_call",
        )

        from app.db.models.ops import UsageLog
        db.add(
            UsageLog(
                user_id=user_id,
                report_id=report_id,
                phase="generation",
                provider=provider_result.provider,
                model=provider_result.model,
                input_tokens=provider_result.input_tokens,
                output_tokens=provider_result.output_tokens,
            )
        )
        db.flush()

        report_status_service.update_report_status(
            db,
            user_id=user_id,
            report_id=report_id,
            new_status=_REVIEW_1,
            commit=False,
        )
        db.commit()
    except GenerationAlreadySucceeded:
        raise
    except Exception:
        db.rollback()
        raise

def _fail_attempt_and_report(
    db: Session,
    *,
    attempt_id: uuid.UUID,
    user_id: uuid.UUID,
    report_id: uuid.UUID,
    error_code: str,
) -> None:
    """Mark a running attempt as permanently failed and fail the report.

    Race-safe counterpart to ``_persist_success_atomic``.

    The success path holds a row lock on the GenerationRun via its
    conditional ``UPDATE ... WHERE status='running'``. This helper
    takes the same row lock here with ``SELECT ... FOR UPDATE`` so
    that the two terminal decisions are serialized. A late permanent
    failure therefore observes the terminal state and no-ops instead
    of overwriting a successful generation.

    Lock order matches the success path: GenerationRun -> Report.
    """
    try:
        run = db.execute(
            select(GenerationRun)
            .where(GenerationRun.id == attempt_id)
            .with_for_update()
        ).scalar_one_or_none()

        # Missing row, or already terminal (success / failed /
        # cancelled): never overwrite. Roll back so the FOR UPDATE
        # lock is released before returning.
        if run is None or run.status != "running":
            db.rollback()
            return

        oj = dict(run.output_json or {})
        oj["attempt_status"] = "failed"
        oj["error_code"] = error_code
        run.output_json = oj
        run.status = "failed"
        run.completed_at = datetime.now(UTC)
        db.flush()

        report = db.execute(
            select(Report)
            .where(
                Report.id == report_id,
                Report.user_id == user_id,
                Report.deleted_at.is_(None),
            )
            .with_for_update()
        ).scalar_one_or_none()
        if report is not None and report.status == _GENERATING:
            report_status_service.update_report_status(
                db,
                user_id=user_id,
                report_id=report_id,
                new_status=_FAILED,
                commit=False,
            )
        db.commit()
    except Exception:
        db.rollback()
        raise


def _load_report(  # noqa: ANN001
    db: Session, user_id: uuid.UUID, report_id: uuid.UUID
):  # noqa: ANN202
    from app.services.reports import get_report
    return get_report(db, user_id=user_id, report_id=report_id)


__all__ = ["generate_report"]
