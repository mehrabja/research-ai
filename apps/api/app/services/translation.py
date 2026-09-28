"""M16 — Translation orchestrator."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.knowledge import TerminologyGlossary
from app.db.models.pipeline import TranslationRun, TranslationVersion
from app.db.models.project import Project
from app.db.models.report import Report, ReportVersion, ReviewEvent
from app.domain.translation_preservation import (
    validate_translation_preservation,
)
from app.integrations.translation.base import (
    TranslationAuthenticationError,
    TranslationInputTooLargeError,
    TranslationInvalidRequestError,
    TranslationInvalidResponseError,
    TranslationProvider,
    TranslationProviderResult,
    TranslationProviderUnavailableError,
    TranslationRateLimitError,
    TranslationTimeoutError,
)
from app.services.report_status import update_report_status
from app.services.translation_profile import TranslationProfile
from app.services.usage_contract import ProviderUsage, record_provider_usage

logger = logging.getLogger(__name__)


class TranslationError(Exception): ...
class TranslationAlreadySucceeded(TranslationError): ...
class TranslationStateError(TranslationError): ...
class TranslationPreservationError(TranslationError): ...
class TranslationValidationError(TranslationError): ...


@dataclass(frozen=True)
class TranslationOutcome:
    run_id: uuid.UUID
    version_id: uuid.UUID
    status: str
    target_language: str


# -------- locks (order: Report first, then TranslationRun) ----------------

def _lock_report(db: Session, report_id: uuid.UUID) -> Report:
    return db.execute(
        select(Report)
        .where(Report.id == report_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).scalar_one()


def _lock_run(db: Session, run_id: uuid.UUID) -> TranslationRun:
    return db.execute(
        select(TranslationRun)
        .where(TranslationRun.id == run_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).scalar_one()


# -------- source resolution ----------------------------------------------

def _resolve_m15_approved_version(
    db: Session, *, report_id: uuid.UUID
) -> ReportVersion | None:
    event = db.execute(
        select(ReviewEvent)
        .where(
            ReviewEvent.report_id == report_id,
            ReviewEvent.stage == "pre_translation",
            ReviewEvent.action == "approved",
        )
        .order_by(ReviewEvent.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    if event is None or event.version_id is None:
        return None
    return db.execute(
        select(ReportVersion).where(
            ReportVersion.id == event.version_id,
            ReportVersion.report_id == report_id,
        )
    ).scalar_one_or_none()


# -------- glossary -------------------------------------------------------

def _load_locked_glossary_pairs(
    db: Session,
    *,
    source_language: str,
    target_language: str,
    domain: str | None,
) -> list[tuple[str, str]]:
    lang_pair = f"{source_language}:{target_language}"
    rows = db.execute(
        select(TerminologyGlossary).where(
            TerminologyGlossary.locked.is_(True),
            TerminologyGlossary.language_pair == lang_pair,
        )
    ).scalars().all()
    if domain:
        rows = [r for r in rows if r.domain in (None, domain)]
    return [(r.source_term, r.target_term) for r in rows]


# -------- identity helpers -----------------------------------------------

def _find_existing_success(
    db: Session,
    *,
    report_id: uuid.UUID,
    source_version_id: uuid.UUID,
    source_lang: str,
    target_lang: str,
    profile_id: str,
) -> TranslationRun | None:
    return db.execute(
        select(TranslationRun).where(
            TranslationRun.report_id == report_id,
            TranslationRun.source_version_id == source_version_id,
            TranslationRun.source_lang == source_lang,
            TranslationRun.target_lang == target_lang,
            TranslationRun.profile_id == profile_id,
            TranslationRun.status == "success",
        )
    ).scalar_one_or_none()


def _get_or_create_running_run(
    db: Session,
    *,
    report_id: uuid.UUID,
    source_version_id: uuid.UUID,
    source_lang: str,
    target_lang: str,
    provider: str,
    profile_id: str,
) -> tuple[TranslationRun, bool]:
    existing = db.execute(
        select(TranslationRun).where(
            TranslationRun.report_id == report_id,
            TranslationRun.source_version_id == source_version_id,
            TranslationRun.source_lang == source_lang,
            TranslationRun.target_lang == target_lang,
            TranslationRun.profile_id == profile_id,
            TranslationRun.status == "running",
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing, False

    run = TranslationRun(
        report_id=report_id,
        generation_run_id=None,
        source_version_id=source_version_id,
        profile_id=profile_id,
        source_lang=source_lang,
        target_lang=target_lang,
        provider=provider,
        status="running",
    )
    db.add(run)
    db.flush()
    return run, True


# -------- failure --------------------------------------------------------

def _fail_run_and_report(
    *,
    db: Session,
    run_id: uuid.UUID,
    report_id: uuid.UUID,
    user_id: uuid.UUID,
    error_code: str,
) -> None:
    """Lock order: Report first, then TranslationRun."""
    locked_report = _lock_report(db, report_id)
    locked_run = _lock_run(db, run_id)

    if locked_run.status in ("success", "failed"):
        db.commit()
        return

    locked_run.status = "failed"
    locked_run.completed_at = datetime.now(UTC)

    if locked_report.status == "translating":
        update_report_status(
            db,
            user_id=user_id,
            report_id=report_id,
            new_status="failed",
            reason=f"translation_failed:{error_code}",
            commit=False,
        )
    db.commit()


def finalize_exhausted_translation(
    *,
    db: Session,
    report_id: uuid.UUID,
    user_id: uuid.UUID,
    error_code: str = "retries_exhausted",
) -> None:
    """Public hook for worker/runner when retries are exhausted."""
    running = db.execute(
        select(TranslationRun).where(
            TranslationRun.report_id == report_id,
            TranslationRun.status == "running",
        )
    ).scalars().all()
    if not running:
        return
    for run in running:
        _fail_run_and_report(
            db=db,
            run_id=run.id,
            report_id=report_id,
            user_id=user_id,
            error_code=error_code,
        )


# -------- usage ----------------------------------------------------------

def _record_translation_usage(
    *,
    db: Session,
    user_id: uuid.UUID,
    report_id: uuid.UUID,
    provider: str,
    model: str,
    input_tokens: int | None,
    output_tokens: int | None,
    idempotency_key: str,
) -> None:
    """Record UsageLog in the same finalization transaction.

    VERIFY: field names against the real ``UsageLog`` model. Adapt
    ``phase``/``provider``/``model`` if the repository uses different
    attribute names.
    """
    from app.db.models.ops import UsageLog  # VERIFY: exact module

    project_id = db.execute(
        select(Report.project_id).where(Report.id == report_id)
    ).scalar_one_or_none()
    project = db.get(Project, project_id) if project_id is not None else None

    total_tokens = (input_tokens or 0) + (output_tokens or 0)
    if project is not None:
        record_provider_usage(
            db,
            workspace_id=project.workspace_id,
            user_id=user_id,
            source_id=None,
            usage=ProviderUsage(
                capability="translation",
                operation="report_translation",
                provider=provider,
                model=model,
                input_tokens=input_tokens or 0,
                output_tokens=output_tokens or 0,
                units=max(1, total_tokens),
                metadata={"report_id": str(report_id)},
            ),
            idempotency_key=idempotency_key.replace(
                ":provider_call",
                ":workspace_provider_call",
            ),
        )

    db.add(
        UsageLog(
            user_id=user_id,
            report_id=report_id,
            phase="translation",
            provider=provider,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            idempotency_key=idempotency_key,
        )
    )
    db.flush()


# -------- main entry ------------------------------------------------------

def translate_report(
    *,
    db: Session,
    user_id: uuid.UUID,
    report_id: uuid.UUID,
    source_version_id: uuid.UUID,
    target_language: str,
    provider: TranslationProvider,
    profile: TranslationProfile,
) -> TranslationOutcome:
    # ---- 1. Validate report ----
    report = db.execute(
        select(Report).where(Report.id == report_id)
    ).scalar_one_or_none()
    if report is None or getattr(report, "deleted_at", None) is not None:
        raise TranslationError("report not found")
    if report.user_id != user_id:
        raise TranslationError("report ownership mismatch")

    if report.status not in ("translating", "post_translation_review"):
        raise TranslationStateError(
            f"report status {report.status!r} not eligible for translation"
        )

    # ---- 2. Validate source = M15-approved version ----
    source_version = db.execute(
        select(ReportVersion).where(
            ReportVersion.id == source_version_id,
            ReportVersion.report_id == report_id,
        )
    ).scalar_one_or_none()
    if source_version is None:
        raise TranslationValidationError("source version not found")

    approved = _resolve_m15_approved_version(db, report_id=report_id)
    if approved is None or approved.id != source_version_id:
        raise TranslationValidationError(
            "source_version_id is not the M15-approved version"
        )

    source_lang = source_version.language
    if not source_lang:
        raise TranslationValidationError("source version has no language")
    if not target_language:
        raise TranslationValidationError("target language missing")

    content = source_version.content or ""
    if not content.strip():
        raise TranslationValidationError("source content is empty")
    if len(content) > profile.max_input_chars:
        raise TranslationValidationError(
            f"source content length {len(content)} exceeds "
            f"max_input_chars {profile.max_input_chars}"
        )

    profile_id = profile.profile_id
    same_language = source_lang == target_language

    # ---- 3. Idempotency: already succeeded? ----
    already = _find_existing_success(
        db,
        report_id=report_id,
        source_version_id=source_version_id,
        source_lang=source_lang,
        target_lang=target_language,
        profile_id=profile_id,
    )
    if already is not None:
        tv = db.execute(
            select(TranslationVersion).where(
                TranslationVersion.translation_run_id == already.id
            )
        ).scalar_one()
        raise TranslationAlreadySucceeded(
            f"translation already succeeded run_id={already.id} "
            f"version_id={tv.id}"
        )

    # ---- 4. Acquire / resume run ----
    db.execute(
        select(Report.id).where(Report.id == report_id).with_for_update()
    )
    run, _ = _get_or_create_running_run(
        db,
        report_id=report_id,
        source_version_id=source_version_id,
        source_lang=source_lang,
        target_lang=target_language,
        provider=provider.provider_name,
        profile_id=profile_id,
    )
    db.commit()

    # ---- 5. Same-language: permanent fail (no provider call) ----
    if same_language:
        _fail_run_and_report(
            db=db,
            run_id=run.id,
            report_id=report_id,
            user_id=user_id,
            error_code="same_language",
        )
        raise TranslationValidationError(
            f"source language equals target language ({source_lang!r})"
        )

    # ---- 6. Glossary read-only → CLOSE transaction before HTTP ----
    glossary_pairs = _load_locked_glossary_pairs(
        db,
        source_language=source_lang,
        target_language=target_language,
        domain=getattr(report, "domain", None),
    )
    db.commit()  # NO open transaction while provider HTTP runs

    # ---- 7. Provider call + preservation retry loop (no DB txn) ----
    last_result: TranslationProviderResult | None = None
    preservation = None

    for attempt in range(profile.preservation_retry_count + 1):
        try:
            result = provider.translate(
                source_text=content,
                source_language=source_lang,
                target_language=target_language,
                instructions=(
                    "Preserve all evidence markers, URLs, DOIs, "
                    "numbers, and locked terminology exactly."
                ),
                temperature=profile.temperature,
                max_output_tokens=profile.max_output_tokens,
            )
        except (
            TranslationRateLimitError,
            TranslationTimeoutError,
            TranslationProviderUnavailableError,
        ):
            # Retryable: leave run=running; queue retries.
            raise
        except (
            TranslationAuthenticationError,
            TranslationInvalidRequestError,
            TranslationInvalidResponseError,
            TranslationInputTooLargeError,
        ) as exc:
            _fail_run_and_report(
                db=db,
                run_id=run.id,
                report_id=report_id,
                user_id=user_id,
                error_code=type(exc).__name__,
            )
            raise

        last_result = result
        preservation = validate_translation_preservation(
            source_text=content,
            target_text=result.translated_text,
            glossary_pairs=glossary_pairs,
        )
        if preservation.ok:
            break
        if attempt >= profile.preservation_retry_count:
            break

    assert last_result is not None
    assert preservation is not None

    if not preservation.ok:
        _fail_run_and_report(
            db=db,
            run_id=run.id,
            report_id=report_id,
            user_id=user_id,
            error_code="preservation_error",
        )
        raise TranslationPreservationError(
            "translation failed preservation validation"
        )

    output_text = last_result.translated_text
    if len(output_text) > profile.max_output_chars:
        _fail_run_and_report(
            db=db,
            run_id=run.id,
            report_id=report_id,
            user_id=user_id,
            error_code="output_too_large",
        )
        raise TranslationValidationError(
            f"translated output length {len(output_text)} exceeds "
            f"max_output_chars {profile.max_output_chars}"
        )

    # ---- 8. Atomic finalization (lock order Report → TranslationRun) ----
    locked_report = _lock_report(db, report_id)
    if locked_report.status not in ("translating", "post_translation_review"):
        db.rollback()
        raise TranslationStateError(
            f"report status {locked_report.status!r} during finalization"
        )

    locked_run = _lock_run(db, run.id)

    if locked_run.status == "success":
        existing_tv = db.execute(
            select(TranslationVersion).where(
                TranslationVersion.translation_run_id == locked_run.id
            )
        ).scalar_one()
        db.commit()
        raise TranslationAlreadySucceeded(
            f"translation already succeeded run_id={locked_run.id} "
            f"version_id={existing_tv.id}"
        )

    if locked_run.status != "running":
        db.rollback()
        raise TranslationStateError(
            f"translation run status {locked_run.status!r} is not running"
        )

    version = TranslationVersion(
        translation_run_id=locked_run.id,
        content=output_text,
        preservation_check_status="passed",
        preservation_details=preservation.to_jsonable(),
    )
    db.add(version)
    db.flush()

    _record_translation_usage(
        db=db,
        user_id=user_id,
        report_id=report_id,
        provider=last_result.provider,
        model=last_result.model,
        input_tokens=last_result.input_tokens,
        output_tokens=last_result.output_tokens,
        idempotency_key=f"translation:{locked_run.id}:provider_call",
    )

    locked_run.status = "success"
    locked_run.completed_at = datetime.now(UTC)

    update_report_status(
        db,
        user_id=user_id,
        report_id=report_id,
        new_status="post_translation_review",
        reason="translation_success",
        commit=False,
    )
    db.commit()
    db.refresh(version)

    return TranslationOutcome(
        run_id=locked_run.id,
        version_id=version.id,
        status="success",
        target_language=target_language,
    )
