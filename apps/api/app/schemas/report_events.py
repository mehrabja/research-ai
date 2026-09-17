"""Report event response schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class ReportEventResponse(BaseModel):
    """Read-only projection of a ``ReportEvent`` row.

    The Python attribute on the ORM model is ``event_meta`` (because
    ``metadata`` is reserved on SQLAlchemy declarative classes), but
    the JSON field name on the wire is ``metadata`` — matching the
    underlying DB column.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    report_id: uuid.UUID
    user_id: uuid.UUID | None
    event_type: str
    from_status: str | None
    to_status: str | None
    version_id: uuid.UUID | None
    metadata: dict | None = Field(
        default=None,
        validation_alias=AliasChoices("event_meta", "metadata"),
    )
    created_at: datetime
