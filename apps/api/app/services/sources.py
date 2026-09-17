"""Source service.

Ownership filtering lives inside the SQL query, not only in the route.
This makes ownership part of the data-access boundary and prevents
cross-user access even if a future caller bypasses the HTTP route.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import SourceNotFound
from app.db.models.source import Source
from app.services.reports import get_report


def get_source_for_report(
    db: Session,
    *,
    user_id: uuid.UUID,
    report_id: uuid.UUID,
    source_id: uuid.UUID,
) -> Source:
    """Return a source that belongs to the given report and user.

    Raises ``ReportNotFound`` if the report is missing, foreign, or
    soft-deleted. Raises ``SourceNotFound`` if the source is missing
    or does not belong to the report.

    Ownership is enforced by reusing ``get_report``, so the same
    contract that protects every other report-scoped resource
    protects sources too.
    """
    get_report(db, user_id=user_id, report_id=report_id)

    stmt = select(Source).where(
        Source.id == source_id,
        Source.report_id == report_id,
    )
    source = db.execute(stmt).scalar_one_or_none()
    if source is None:
        raise SourceNotFound()
    return source


__all__ = ["get_source_for_report"]
