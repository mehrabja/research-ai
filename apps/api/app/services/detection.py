"""Detection service."""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal, cast

from sqlalchemy import CursorResult, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import (
    DetectionAlreadyCompletedError,
    InvalidJobStateError,
)
from app.db.models.pipeline import DetectionRun
from app.db.models.report import Report, ReportVersion
from app.domain.detection import (
    DetectionLabel,
    DetectionProfile,
    DetectionProviderResult,
    DetectionResult,
    build_detection_profile_id,
    hash_detection_input,
)
from app.integrations.detection.base import (
    DetectionAuthenticationError,
    DetectionInputTooLargeError,
    DetectionInvalidRequestError,
    DetectionInvalidResponseError,
    DetectionProvider,
)
from app.services import report_status as report_status_service
from app.services.detection_profile import (
    get_current_detection_profile,
)

logger = logging.getLogger(__name__)

_DETECTING = "detecting"
_HUMANIZING = "humanizing"
_FAILED = "failed"

_DETECTION_IDENTITY_CONSTRAINT = "ux_detection_runs_identity"

_PERMANENT_ERRORS: tuple[type[BaseException], ...] = (
    DetectionAuthenticationError,
    DetectionInputTooLargeError,
    DetectionInvalidRequestError,
    DetectionInvalidResponseError,
)


AttemptState = Literal["created", "existing_running"]


@dataclass(frozen=True)
class _AttemptLease:
    run_id: uuid.UUID
    state: AttemptState
    report_domain: str | None


def _is_permanent(exc: BaseException) -> bool:
    return isinstance(exc, _PERMANENT_ERRORS)


def _error_code_for(exc: BaseException) -> str:
    if isinstance(exc, DetectionAuthenticationError):
        return "authentication_error"
    if isinstance(exc, DetectionInputTooLargeError):
        return "input_too_large"
    if isinstance(exc, DetectionInvalidRequestError):
        return "invalid_payload"
    if isinstance(exc, DetectionInvalidResponseError):
        return "invalid_provider_response"
    return "permanent_detection_error"


def _is_detection_identity_unique_violation(
    exc: IntegrityError,
) -> bool:
    orig = exc.orig
    constraint_name = getattr(orig, "constraint_name", None)
    if constraint_name == _DETECTION_IDENTITY_CONSTRAINT:
        return True
    diag = getattr(orig, "diag", None)
    diag_constraint = getattr(diag, "constraint_name", None)
    return diag_constraint == _DETECTION_IDENTITY_CONSTRAINT


def _existing_completed(
    db: Session,
    *,
    report_id: uuid.UUID,
    version_id: uuid.UUID,
    profile_id: str,
    input_hash: str,
) -> DetectionRun | None:
    return db.execute(
        select(DetectionRun).where(
            DetectionRun.report_id == report_id,
            DetectionRun.version_id == version_id,
            DetectionRun.profile_id == profile_id,
            DetectionRun.input_hash == input_hash,
            DetectionRun.status == "completed",
        )
    ).scalar_one_or_none()


def _existing_running_same_identity(
    db: Session,
    *,
    report_id: uuid.UUID,
    version_id: uuid.UUID,
    profile_id: str,
    input_hash: str,
) -> DetectionRun | None:
    return db.execute(
        select(DetectionRun).where(
            DetectionRun.report_id == report_id,
            DetectionRun.version_id == version_id,
            DetectionRun.profile_id == profile_id,
            DetectionRun.input_hash == input_hash,
            DetectionRun.status == "running",
        )
    ).scalar_one_or_none()


def _acquire_attempt_or_short_circuit(
    db: Session,
    *,
    user_id: uuid.UUID,
    report_id: uuid.UUID,
    version_id: uuid.UUID,
    profile_id: str,
    input_hash: str,
    input_chars: int,
    provider: DetectionProvider,
) -> _AttemptLease:
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

    version = db.execute(
        select(ReportVersion).where(
            ReportVersion.id == version_id,
            ReportVersion.report_id == report_id,
        )
    ).scalar_one_or_none()
    if version is None:
        from app.core.exceptions import ReportVersionNotFound
        raise ReportVersionNotFound()

    if (
        _existing_completed(
            db,
            report_id=report_id,
            version_id=version_id,
            profile_id=profile_id,
            input_hash=input_hash,
        )
        is not None
    ):
        raise DetectionAlreadyCompletedError()

    if report.status == "review_1":
        report_status_service.update_report_status(
            db,
            user_id=user_id,
            report_id=report_id,
            new_status=_DETECTING,
            commit=False,
        )
    elif report.status == _DETECTING:
        pass
    else:
        raise InvalidJobStateError(
            f"cannot detect from status {report.status!r}"
        )

    running = _existing_running_same_identity(
        db,
        report_id=report_id,
        version_id=version_id,
        profile_id=profile_id,
        input_hash=input_hash,
    )
    if running is not None:
        return _AttemptLease(
            run_id=running.id,
            state="existing_running",
            report_domain=report.domain,
        )

    any_other_running = db.execute(
        select(DetectionRun.id)
        .where(
            DetectionRun.report_id == report_id,
            DetectionRun.status == "running",
        )
        .limit(1)
    ).scalar_one_or_none()
    if any_other_running is not None:
        raise InvalidJobStateError(
            "report already has an active detection for another version"
        )

    run = DetectionRun(
        report_id=report_id,
        version_id=version_id,
        scanned_text_version=str(version_id),
        provider=provider.provider_name,
        profile_id=profile_id,
        input_hash=input_hash,
        input_chars=input_chars,
        status="running",
        detection_meta={
            "provider": provider.provider_name,
            "model": provider.model_name,
            "profile_id": profile_id,
            "input_hash": input_hash,
            "input_chars": input_chars,
        },
    )
    db.add(run)
    db.flush()
    return _AttemptLease(
        run_id=run.id,
        state="created",
        report_domain=report.domain,
    )


def _classify_label(
    db: Session,
    *,
    probability: float | None,
    provider: str,
    domain: str | None,
    language: str,
) -> DetectionLabel:
    if probability is None:
        return "unknown"

    from app.db.models.knowledge import DetectionThreshold

    stmt = (
        select(DetectionThreshold)
        .where(
            DetectionThreshold.detector == provider,
            DetectionThreshold.language == language,
        )
        .order_by(DetectionThreshold.domain.asc())
    )
    rows = list(db.execute(stmt).scalars().all())
    if not rows:
        return "unknown"

    chosen = None
    if domain:
        for r in rows:
            if r.domain == domain:
                chosen = r
                break
    if chosen is None:
        for r in rows:
            if r.domain == "general":
                chosen = r
                break
    if chosen is None:
        chosen = rows[0]

    p = chosen.percentiles or {}
    low_boundary = p.get("low")
    high_boundary = p.get("high")
    if isinstance(low_boundary, (int, float)) and isinstance(
        high_boundary, (int, float)
    ):
        if probability < float(low_boundary):
            return "low"
        if probability >= float(high_boundary):
            return "high"
        return "medium"

    t = chosen.threshold
    if t is None:
        return "unknown"
    t_float = float(t)
    if probability < t_float:
        return "low"
    return "medium"


def detect_report_version(
    db: Session,
    *,
    user_id: uuid.UUID,
    report_id: uuid.UUID,
    version_id: uuid.UUID,
    provider: DetectionProvider,
    profile: DetectionProfile | None = None,
) -> DetectionResult:
    profile = profile or get_current_detection_profile()
    profile_id = build_detection_profile_id(profile)

    version = db.execute(
        select(ReportVersion).where(
            ReportVersion.id == version_id,
            ReportVersion.report_id == report_id,
        )
    ).scalar_one_or_none()
    if version is None:
        from app.core.exceptions import ReportVersionNotFound
        raise ReportVersionNotFound()

    text = version.content or ""
    input_hash = hash_detection_input(text)
    input_chars = len(text)

    try:
        lease = _acquire_attempt_or_short_circuit(
            db,
            user_id=user_id,
            report_id=report_id,
            version_id=version_id,
            profile_id=profile_id,
            input_hash=input_hash,
            input_chars=input_chars,
            provider=provider,
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if _is_detection_identity_unique_violation(exc):
            raise DetectionAlreadyCompletedError() from exc
        raise
    except DetectionAlreadyCompletedError:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise

    attempt_id = lease.run_id

    if input_chars < profile.minimum_text_chars:
        _persist_unknown_atomic(
            db,
            attempt_id=attempt_id,
            user_id=user_id,
            report_id=report_id,
            profile_id=profile_id,
            input_hash=input_hash,
            input_chars=input_chars,
            provider=provider,
            reason="insufficient_text",
        )
        return DetectionResult(
            probability=None,
            label="unknown",
            provider=provider.provider_name,
            model=provider.model_name,
            profile_id=profile_id,
            input_hash=input_hash,
            input_chars=input_chars,
        )

    try:
        provider_result: DetectionProviderResult = provider.detect(
            text=text
        )
    except BaseException as exc:
        if _is_permanent(exc):
            _fail_attempt_and_report(
                db,
                attempt_id=attempt_id,
                user_id=user_id,
                report_id=report_id,
                error_code=_error_code_for(exc),
            )
        raise

    label = _classify_label(
        db,
        probability=provider_result.probability,
        provider=provider_result.provider,
        domain=lease.report_domain,
        language=version.language,
    )

    _persist_success_atomic(
        db,
        attempt_id=attempt_id,
        user_id=user_id,
        report_id=report_id,
        provider_result=provider_result,
        label=label,
        profile_id=profile_id,
        input_hash=input_hash,
        input_chars=input_chars,
    )

    return DetectionResult(
        probability=provider_result.probability,
        label=label,
        provider=provider_result.provider,
        model=provider_result.model,
        profile_id=profile_id,
        input_hash=input_hash,
        input_chars=input_chars,
    )


def _persist_success_atomic(
    db: Session,
    *,
    attempt_id: uuid.UUID,
    user_id: uuid.UUID,
    report_id: uuid.UUID,
    provider_result: DetectionProviderResult,
    label: str,
    profile_id: str,
    input_hash: str,
    input_chars: int,
) -> None:
    try:
        result = cast(
            CursorResult,
            db.execute(
                update(DetectionRun)
                .where(
                    DetectionRun.id == attempt_id,
                    DetectionRun.status == "running",
                )
                .values(
                    status="completed",
                    overall_score=provider_result.probability,
                    completed_at=datetime.now(UTC),
                    detection_meta={
                        "provider": provider_result.provider,
                        "model": provider_result.model,
                        "profile_id": profile_id,
                        "input_hash": input_hash,
                        "input_chars": input_chars,
                        "label": label,
                        "details": dict(provider_result.details or {}),
                    },
                )
            ),
        )
        if result.rowcount == 0:
            raise DetectionAlreadyCompletedError()

        report_status_service.update_report_status(
            db,
            user_id=user_id,
            report_id=report_id,
            new_status=_HUMANIZING,
            commit=False,
        )
        db.commit()
    except DetectionAlreadyCompletedError:
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        if _is_detection_identity_unique_violation(exc):
            raise DetectionAlreadyCompletedError() from exc
        raise
    except Exception:
        db.rollback()
        raise


def _persist_unknown_atomic(
    db: Session,
    *,
    attempt_id: uuid.UUID,
    user_id: uuid.UUID,
    report_id: uuid.UUID,
    profile_id: str,
    input_hash: str,
    input_chars: int,
    provider: DetectionProvider,
    reason: str,
) -> None:
    try:
        result = cast(
            CursorResult,
            db.execute(
                update(DetectionRun)
                .where(
                    DetectionRun.id == attempt_id,
                    DetectionRun.status == "running",
                )
                .values(
                    status="completed",
                    overall_score=None,
                    completed_at=datetime.now(UTC),
                    detection_meta={
                        "provider": provider.provider_name,
                        "model": provider.model_name,
                        "profile_id": profile_id,
                        "input_hash": input_hash,
                        "input_chars": input_chars,
                        "label": "unknown",
                        "reason": reason,
                    },
                )
            ),
        )
        if result.rowcount == 0:
            raise DetectionAlreadyCompletedError()

        report_status_service.update_report_status(
            db,
            user_id=user_id,
            report_id=report_id,
            new_status=_HUMANIZING,
            commit=False,
        )
        db.commit()
    except DetectionAlreadyCompletedError:
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        if _is_detection_identity_unique_violation(exc):
            raise DetectionAlreadyCompletedError() from exc
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
    try:
        run = db.execute(
            select(DetectionRun)
            .where(
                DetectionRun.id == attempt_id,
                DetectionRun.status == "running",
            )
            .with_for_update()
        ).scalar_one_or_none()
        if run is None:
            db.rollback()
            return

        oj = dict(run.detection_meta or {})
        oj["error_code"] = error_code
        run.detection_meta = oj
        run.status = "failed"
        run.completed_at = datetime.now(UTC)
        db.flush()

        row = db.execute(
            select(Report)
            .where(
                Report.id == report_id,
                Report.user_id == user_id,
                Report.deleted_at.is_(None),
            )
            .with_for_update()
        ).scalar_one_or_none()
        if row is not None and row.status == _DETECTING:
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


__all__ = [
    "detect_report_version",
    "_is_detection_identity_unique_violation",
]
