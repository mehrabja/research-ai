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
    commit: bool = True,
) -> Report:
    """Change a report's status and record an audit event atomically."""
    report = get_report(
        db,
        user_id=user_id,
        report_id=report_id,
    )

    current_status = report.status

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
        create_status_transition_event(
            db,
            report_id=report_id,
            user_id=user_id,
            from_status=current_status,
            to_status=new_status,
        )
        if commit:
            db.commit()
            db.refresh(report)
        else:
            db.flush()
    except Exception:
        db.rollback()
        raise

    return report
