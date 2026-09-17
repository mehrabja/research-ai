"""Canonical report event types.

Single source of truth for the *set* of valid ``report_events.event_type``
values. The DB ``ck_report_events_type`` CHECK constraint mirrors this
set exactly; any drift is a bug.

Historical note
---------------
``source_added`` is intentionally NOT part of this set: the sources
foundation milestone was never applied to this repository. Only the
three event types below exist:

  * ``status_transition`` — a report moved between two statuses
  * ``version_created``   — a new immutable report version was created
  * ``source_extracted``  — a source document was fetched, extracted,
    and chunked
"""
from __future__ import annotations

from typing import Literal

ReportEventType = Literal[
    "status_transition",
    "version_created",
    "source_extracted",
]


ALL_REPORT_EVENT_TYPES: tuple[ReportEventType, ...] = (
    "status_transition",
    "version_created",
    "source_extracted",
)


__all__ = ["ALL_REPORT_EVENT_TYPES", "ReportEventType"]
