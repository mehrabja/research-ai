"""M17 — Post-translation detection (same-run stale recovery)."""

from __future__ import annotations

import logging
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models.pipeline import DetectionRun, DetectionSegment
from app.db.models.report import Report, ReportVersion
from app.domain.humanization import sha256_hex

logger = logging.getLogger(__name__)


class PostTranslationDetectionError(Exception): ...
class PostTranslationDetectionOwnershipLostError(PostTranslationDetectionError): ...
class PostTranslationDetectionNoSegmentContractError(PostTranslationDetectionError): ...
class PostTranslationDetectionAlreadyRunningError(PostTranslationDetectionError): ...


def _new_token() -> str:
    return secrets.token_urlsafe(20)


def _profile_id(profile: Any) -> str:
    for attr in ("profile_id", "id"):
        v = getattr(profile, attr, None)
        if isinstance(v, str) and v:
            return v
    raise PostTranslationDetectionError("detection profile has no profile_id")


def _minimum_text_chars(profile: Any) -> int:
    return int(getattr(profile, "minimum_text_chars", 0) or 0)


def _lock_report(db: Session, report_id: uuid.UUID) -> Report:
    return db.execute(
        select(Report)
        .where(Report.id == report_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).scalar_one()


def _max_provider_window_seconds() -> float:
    s = get_settings()
    timeout = float(getattr(s, "detection_timeout_seconds", 60.0))
    retries = int(getattr(s, "detection_max_retries", 2))
    retry_max = float(getattr(s, "detection_retry_max_seconds", 30.0))
    return timeout * (retries + 1) + retry_max * (retries + 1)


def _compute_lease_expiry() -> str:
    s = get_settings()
    margin = s.post_translation_detection_lease_safety_margin_seconds
    delta = _max_provider_window_seconds() + margin
    return (datetime.now(UTC) + timedelta(seconds=delta)).isoformat()


def _lease_expires_at(run: DetectionRun) -> datetime:
    meta = run.detection_meta or {}
    raw = meta.get("lease_expires_at") if isinstance(meta, dict) else None
    if isinstance(raw, str):
        try:
            dt = datetime.fromisoformat(raw)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            return dt
        except ValueError:
            pass
    return datetime.now(UTC)


def _is_stale(run: DetectionRun) -> bool:
    return datetime.now(UTC) > _lease_expires_at(run)


def _touch_lease(*, db: Session, run_id: uuid.UUID, token: str) -> bool:
    """CAS heartbeat + lease expiry refresh; returns True iff token still owns.

    Uses ORM + SELECT ... FOR UPDATE instead of raw SQL to avoid
    parameter type inference issues with ``jsonb_build_object``.
    """
    run = db.execute(
        select(DetectionRun)
        .where(DetectionRun.id == run_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if run is None or run.status != "running":
        db.rollback()
        return False
    meta = run.detection_meta or {}
    if not isinstance(meta, dict) or meta.get("execution_token") != token:
        db.rollback()
        return False
    run.detection_meta = {
        **meta,
        "lease_heartbeat_at": datetime.now(UTC).isoformat(),
        "lease_expires_at": _compute_lease_expiry(),
    }
    db.flush()
    db.commit()
    return True


def _select_one(
    db: Session, *, report_id, version_id, profile_id, input_hash, status,
) -> DetectionRun | None:
    return db.execute(
        select(DetectionRun)
        .where(
            DetectionRun.report_id == report_id,
            DetectionRun.version_id == version_id,
            DetectionRun.profile_id == profile_id,
            DetectionRun.input_hash == input_hash,
            DetectionRun.status == status,
        )
        .order_by(
            DetectionRun.completed_at.desc().nullslast(),
            DetectionRun.created_at.desc(),
        )
        .limit(1)
    ).scalars().first()


def _normalize_segments(details: Any, *, paragraph_count: int) -> list[dict[str, Any]]:
    if not isinstance(details, dict):
        raise PostTranslationDetectionNoSegmentContractError(
            "detector returned no 'details' mapping"
        )
    if "segments" not in details:
        raise PostTranslationDetectionNoSegmentContractError(
            "detector 'details' missing 'segments' key"
        )
    raw = details["segments"]
    if not isinstance(raw, list):
        raise PostTranslationDetectionNoSegmentContractError(
            "'segments' must be a list"
        )
    out: list[dict[str, Any]] = []
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            raise PostTranslationDetectionError(
                f"invalid_segment_payload: segment[{i}] not a mapping"
            )
        idx = item.get("paragraph_index")
        if not isinstance(idx, int) or idx < 0 or idx >= paragraph_count:
            raise PostTranslationDetectionError(
                f"invalid_segment_payload: segment[{i}] paragraph_index "
                f"{idx!r} out of range (paragraph_count={paragraph_count})"
            )
        out.append({
            "paragraph_index": idx,
            "segment_identifier": str(item.get("segment_identifier") or idx),
            "flagged": bool(item.get("flagged", False)),
            "score": item.get("score"),
            "reason": item.get("reason"),
        })
    return out


def _expected_segment_count(meta: Any) -> int:
    if not isinstance(meta, dict):
        return 0
    details = meta.get("details")
    if not isinstance(details, dict):
        return 0
    segs = details.get("segments")
    return len(segs) if isinstance(segs, list) else 0


def _persisted_count(db: Session, run_id: uuid.UUID) -> int:
    return int(
        db.execute(
            select(func.count())
            .select_from(DetectionSegment)
            .where(DetectionSegment.detection_run_id == run_id)
        ).scalar_one()
    )


def _validate_completed_run_metadata(
    *, db: Session, run: DetectionRun, paragraphs: int,
) -> bool:
    meta = run.detection_meta or {}
    if not isinstance(meta, dict):
        return False
    details = meta.get("details")
    if not isinstance(details, dict):
        return False
    segs = details.get("segments")
    if not isinstance(segs, list):
        return False
    expected_indexes: set[int] = set()
    for item in segs:
        if not isinstance(item, dict):
            return False
        idx = item.get("paragraph_index")
        if not isinstance(idx, int) or idx < 0 or idx >= paragraphs:
            return False
        if idx in expected_indexes:
            return False
        expected_indexes.add(idx)
    rows = db.execute(
        select(DetectionSegment).where(
            DetectionSegment.detection_run_id == run.id
        )
    ).scalars().all()
    if len(rows) != len(segs):
        return False
    persisted_indexes: set[int] = set()
    for row in rows:
        if row.paragraph_index is None:
            return False
        if row.paragraph_index in persisted_indexes:
            return False
        persisted_indexes.add(row.paragraph_index)
    return persisted_indexes == expected_indexes


def _mark_failed(
    *, db: Session, run_id: uuid.UUID, token: str, error_code: str,
) -> None:
    try:
        locked = db.execute(
            select(DetectionRun)
            .where(DetectionRun.id == run_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        ).scalar_one_or_none()
    except Exception:
        db.rollback()
        logger.exception(
            "post_translation_detection.mark_failed_lookup_error run_id=%s",
            run_id,
        )
        raise

    if locked is None:
        db.rollback()
        logger.error(
            "post_translation_detection.mark_failed_run_not_found run_id=%s",
            run_id,
        )
        return

    if locked.status == "completed":
        db.commit()
        return

    current_token = (locked.detection_meta or {}).get("execution_token")
    if locked.status != "running" or current_token != token:
        db.rollback()
        raise PostTranslationDetectionOwnershipLostError(
            f"cannot mark failed: token={token} no longer owns run_id={run_id}"
        )

    locked.status = "failed"
    locked.detection_meta = {
        **(locked.detection_meta or {}),
        "error_code": error_code,
    }
    locked.completed_at = datetime.now(UTC)
    db.commit()


def run_post_translation_detection(
    *,
    db: Session,
    report: Report,
    translated_version: ReportVersion,
    detection_provider: Any,
    detection_profile: Any,
) -> DetectionRun:
    profile_id = _profile_id(detection_profile)
    input_hash = sha256_hex(translated_version.content)
    input_chars = len(translated_version.content)
    paragraphs = translated_version.content.split("\n\n")

    _lock_report(db, report.id)

    completed = _select_one(
        db, report_id=report.id, version_id=translated_version.id,
        profile_id=profile_id, input_hash=input_hash, status="completed",
    )
    if completed is not None:
        if _validate_completed_run_metadata(
            db=db, run=completed, paragraphs=len(paragraphs)
        ):
            db.commit()
            return completed
        logger.warning(
            "post_translation_detection.invalid_completed_metadata run_id=%s",
            completed.id,
        )
        completed.status = "failed"
        completed.detection_meta = {
            **(completed.detection_meta or {}),
            "error_code": "invalid_completed_metadata",
        }
        db.flush()

    running = _select_one(
        db, report_id=report.id, version_id=translated_version.id,
        profile_id=profile_id, input_hash=input_hash, status="running",
    )
    if running is not None:
        if not _is_stale(running):
            db.commit()
            raise PostTranslationDetectionAlreadyRunningError(
                f"post-translation detection already running run_id={running.id}"
            )
        locked = db.execute(
            select(DetectionRun)
            .where(DetectionRun.id == running.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        ).scalar_one()
        if locked.status != "running" or not _is_stale(locked):
            db.commit()
            raise PostTranslationDetectionAlreadyRunningError(
                f"detection race on run_id={running.id}"
            )
        token = _new_token()
        locked.detection_meta = {
            **(locked.detection_meta or {}),
            "execution_token": token,
            "lease_heartbeat_at": datetime.now(UTC).isoformat(),
            "lease_expires_at": _compute_lease_expiry(),
        }
        db.commit()
        run_id = locked.id
    else:
        token = _new_token()
        new_run = DetectionRun(
            report_id=report.id,
            generation_run_id=None,
            version_id=translated_version.id,
            profile_id=profile_id,
            input_hash=input_hash,
            input_chars=input_chars,
            scanned_text_version=str(translated_version.id),
            provider=getattr(detection_provider, "provider_name", "unknown"),
            overall_score=None,
            status="running",
            detection_meta={
                "execution_token": token,
                "lease_heartbeat_at": datetime.now(UTC).isoformat(),
                "lease_expires_at": _compute_lease_expiry(),
            },
        )
        db.add(new_run)
        db.commit()
        run_id = new_run.id

    if input_chars < _minimum_text_chars(detection_profile):
        try:
            _finalize_atomic(
                db=db, run_id=run_id, token=token,
                overall_score=None,
                meta={
                    "execution_token": token,
                    "provider": getattr(detection_provider, "provider_name", "unknown"),
                    "model": getattr(detection_provider, "model_name", "unknown"),
                    "profile_id": profile_id,
                    "input_hash": input_hash,
                    "label": "unknown",
                    "reason": "insufficient_text",
                },
                normalized_segments=[],
            )
        except PostTranslationDetectionOwnershipLostError:
            raise
        except Exception as exc:
            _mark_failed(
                db=db, run_id=run_id, token=token,
                error_code="finalize_error",
            )
            raise exc
        return db.get(DetectionRun, run_id)  # type: ignore[return-value]

    if not _touch_lease(db=db, run_id=run_id, token=token):
        db.rollback()
        raise PostTranslationDetectionOwnershipLostError(
            f"detection lease lost before provider call run_id={run_id}"
        )

    try:
        result = detection_provider.detect(text=translated_version.content)
    except Exception:
        _mark_failed(
            db=db, run_id=run_id, token=token, error_code="provider_error",
        )
        raise

    if not _touch_lease(db=db, run_id=run_id, token=token):
        db.rollback()
        raise PostTranslationDetectionOwnershipLostError(
            f"detection lease lost after provider call run_id={run_id}"
        )

    probability = getattr(result, "probability", None)
    label = getattr(result, "label", "unknown")
    details = getattr(result, "details", None)
    overall = float(probability) if probability is not None else None

    try:
        normalized = _normalize_segments(
            details, paragraph_count=len(paragraphs)
        )
    except PostTranslationDetectionNoSegmentContractError:
        _mark_failed(
            db=db, run_id=run_id, token=token,
            error_code="no_segment_contract",
        )
        raise
    except PostTranslationDetectionError:
        _mark_failed(
            db=db, run_id=run_id, token=token,
            error_code="invalid_segment_payload",
        )
        raise

    meta: dict[str, Any] = {
        "execution_token": token,
        "provider": getattr(result, "provider", "openai"),
        "model": getattr(result, "model", getattr(detection_provider, "model_name", "")),
        "profile_id": profile_id,
        "input_hash": input_hash,
        "label": str(label),
    }
    if isinstance(details, dict):
        meta["details"] = details

    try:
        _finalize_atomic(
            db=db, run_id=run_id, token=token,
            overall_score=overall, meta=meta,
            normalized_segments=normalized,
        )
    except PostTranslationDetectionOwnershipLostError:
        raise
    except PostTranslationDetectionError:
        _mark_failed(
            db=db, run_id=run_id, token=token,
            error_code="segment_persistence_mismatch",
        )
        raise
    return db.get(DetectionRun, run_id)  # type: ignore[return-value]


def _finalize_atomic(
    *, db, run_id, token, overall_score, meta, normalized_segments,
) -> None:
    locked = db.execute(
        select(DetectionRun)
        .where(DetectionRun.id == run_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()

    if locked is None:
        db.rollback()
        raise PostTranslationDetectionError(
            f"detection run disappeared run_id={run_id}"
        )
    if locked.status != "running":
        db.rollback()
        raise PostTranslationDetectionOwnershipLostError(
            f"detection run no longer running (status={locked.status!r})"
        )
    current_token = (locked.detection_meta or {}).get("execution_token")
    if current_token != token:
        db.rollback()
        raise PostTranslationDetectionOwnershipLostError(
            f"detection token mismatch run_id={run_id}"
        )

    db.execute(
        delete(DetectionSegment).where(
            DetectionSegment.detection_run_id == locked.id
        )
    )
    for seg in normalized_segments:
        db.add(DetectionSegment(
            detection_run_id=locked.id,
            paragraph_index=seg["paragraph_index"],
            segment_identifier=seg["segment_identifier"],
            score=seg["score"],
            flagged=seg["flagged"],
            reason=seg["reason"],
            segment_meta={},
        ))
    db.flush()

    persisted = _persisted_count(db, locked.id)
    if persisted != len(normalized_segments):
        db.rollback()
        raise PostTranslationDetectionError(
            f"segment persistence mismatch: "
            f"expected {len(normalized_segments)} got {persisted}"
        )

    locked.status = "completed"
    locked.overall_score = overall_score
    locked.detection_meta = {
        **meta,
        "lease_heartbeat_at": datetime.now(UTC).isoformat(),
        "lease_expires_at": _compute_lease_expiry(),
    }
    locked.completed_at = datetime.now(UTC)
    db.commit()
