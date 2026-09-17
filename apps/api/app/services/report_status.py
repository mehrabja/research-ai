"""Report status transition service."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.core.exceptions import InvalidReportTransition
from app.db.models.report import Report
from app.domain.report_status import (
    ALLOWED_REPORT_TRANSITIONS,
)
from app.services.report_events import create_status_transition_event
from app.services.reports import get_report


def update_report_status(
    db: Session,
    *,
    user_id: uuid.UUID,
    report_id: uuid.UUID,
    new_status: str,
) -> Report:
    """Change a report's status and record an audit event atomically.

    The status UPDATE and its ``status_transition`` audit event are
    committed in a single transaction: either both persist or
    neither does. The event insert is deliberately performed with the
    same session and *before* the commit, without an intermediate
    commit between them.
    """
    report = get_report(
        db,
        user_id=user_id,
        report_id=report_id,
    )

    current_status = report.status

    # Idempotent no-op: same-status requests return the unchanged
    # report without writing an event.
    if new_status == current_status:
        return report

    allowed = ALLOWED_REPORT_TRANSITIONS.get(
        current_status,
        frozenset(),
    )

    if new_status not in allowed:
        raise InvalidReportTransition(
            f"Cannot transition report from "
            f"'{current_status}' to '{new_status}'."
        )

    report.status = new_status

    try:
        # Same transaction: build the audit event *before* commit so
        # that a failure on either side rolls back both.
        create_status_transition_event(
            db,
            report_id=report_id,
            user_id=user_id,
            from_status=current_status,
            to_status=new_status,
        )
        db.commit()
        db.refresh(report)
    except Exception:
        db.rollback()
        raise

    return report
