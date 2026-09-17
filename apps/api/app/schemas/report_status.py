"""Report status transition schema."""

from __future__ import annotations

from pydantic import BaseModel

from app.domain.report_status import ReportStatus


class ReportStatusUpdate(BaseModel):
    """Body of PATCH /reports/{report_id}/status."""

    status: ReportStatus
