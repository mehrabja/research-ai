"""Report event service.

Events are append-only. This module NEVER commits: the caller owns the
transaction boundary so that a mutation (status change or version
creation) and its audit event commit atomically.

Callers must not call ``db.commit()`` between the mutation and the
event insert. The outer services (``report_status``, ``report_versions``)
take care of that.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import (
    ReportEventValidationError,
    ReportEventVersionMismatch,
)
from app.db.models.report import ReportEvent, ReportVersion
from app.domain.report_status import ALL_REPORT_STATUSES
from app.services.reports import get_report

_LIST_DEFAULT_LIMIT = 100
_LIST_MAX_LIMIT = 500

_ALL_STATUS_SET = frozenset(ALL_REPORT_STATUSES)


def _validate_status_transition_shape(
    from_status: str,
    to_status: str,
) -> None:
    """Fail-closed validation for ``status_transition`` events.

    The DB CHECK constraint enforces the *shape* (both statuses set,
    distinct, ``version_id`` NULL). This function additionally
    validates that both values are recognized statuses from the
    canonical set, without duplicating the full Report CHECK at the
    DB level.
    """
    if not from_status or not to_status:
        raise ReportEventValidationError(
            "status transition requires non-empty statuses"
        )

    if from_status not in _ALL_STATUS_SET:
        raise ReportEventValidationError(
            f"unknown from_status: {from_status!r}"
        )

    if to_status not in _ALL_STATUS_SET:
        raise ReportEventValidationError(
            f"unknown to_status: {to_status!r}"
        )

    if from_status == to_status:
        raise ReportEventValidationError(
            "status transition requires distinct statuses"
        )


def create_status_transition_event(
    db: Session,
    *,
    report_id: uuid.UUID,
    user_id: uuid.UUID | None,
    from_status: str,
    to_status: str,
    metadata: dict | None = None,
) -> ReportEvent:
    """Add a ``status_transition`` event to the session. Does NOT commit.

    The caller is responsible for committing the same transaction
    that contains the report status mutation, so that both succeed
    or both roll back together.
    """
    _validate_status_transition_shape(from_status, to_status)

    event = ReportEvent(
        report_id=report_id,
        user_id=user_id,
        event_type="status_transition",
        from_status=from_status,
        to_status=to_status,
        version_id=None,
        event_meta=metadata,
    )
    db.add(event)
    return event


def create_version_created_event(
    db: Session,
    *,
    report_id: uuid.UUID,
    user_id: uuid.UUID | None,
    version_id: uuid.UUID,
    metadata: dict | None = None,
) -> ReportEvent:
    """Add a ``version_created`` event to the session. Does NOT commit.

    Guards against cross-report linkage: the referenced version must
    belong to the same report as the event. A plain FK cannot express
    this constraint, so we enforce it here. The caller must have
    already flushed the version so that ``version.id`` is populated.
    """
    version = db.get(ReportVersion, version_id)

    if version is None:
        raise ReportEventVersionMismatch(
            "version_id does not reference an existing version"
        )

    if version.report_id != report_id:
        raise ReportEventVersionMismatch(
            "version_id belongs to a different report"
        )

    event = ReportEvent(
        report_id=report_id,
        user_id=user_id,
        event_type="version_created",
        from_status=None,
        to_status=None,
        version_id=version_id,
        event_meta=metadata,
    )
    db.add(event)
    return event


def list_report_events(
    db: Session,
    *,
    user_id: uuid.UUID,
    report_id: uuid.UUID,
    limit: int | None = None,
) -> list[ReportEvent]:
    """Return events for an owned, active report, newest first.

    Ordering is ``created_at DESC, id DESC``. The ``id`` tie-breaker
    is deterministic, not chronological: PostgreSQL ``now()`` is
    transaction-scoped, so two events created in the same transaction
    may share ``created_at``. The UUID tie-breaker keeps ordering
    stable across identical timestamps.

    Raises ``ReportNotFound`` if the report is missing, foreign, or
    soft-deleted (same contract used everywhere else).
    """
    # Ownership + active + non-deleted check.
    get_report(db, user_id=user_id, report_id=report_id)

    effective_limit = _LIST_DEFAULT_LIMIT if limit is None else limit
    if effective_limit <= 0:
        effective_limit = _LIST_DEFAULT_LIMIT
    if effective_limit > _LIST_MAX_LIMIT:
        effective_limit = _LIST_MAX_LIMIT

    stmt = (
        select(ReportEvent)
        .where(ReportEvent.report_id == report_id)
        .order_by(
            ReportEvent.created_at.desc(),
            ReportEvent.id.desc(),
        )
        .limit(effective_limit)
    )
    return list(db.execute(stmt).scalars().all())
