"""Report status: canonical type and state machine.

The DB ``reports.status`` CHECK constraint enforces the *set* of valid
status values. This module enforces the *transitions* between them.
Both are needed and complementary:

    DB CHECK                -> "is this a real status?"
    State machine (here)    -> "is this a legal transition?"

Single source of truth for the status values used by:
  * Pydantic schemas
  * Services
  * Tests
"""
from __future__ import annotations

from typing import Literal

ReportStatus = Literal[
    "draft",
    "searching",
    "extracting",
    "retrieving",
    "generating",
    "review_1",
    "detecting",
    "humanizing",
    "translating",
    "post_translation_review",
    "converging",
    "review_2",
    "validating",
    "completed",
    "failed",
    "cancelled",
]

ALL_REPORT_STATUSES: tuple[ReportStatus, ...] = (
    "draft",
    "searching",
    "extracting",
    "retrieving",
    "generating",
    "review_1",
    "detecting",
    "humanizing",
    "translating",
    "post_translation_review",
    "converging",
    "review_2",
    "validating",
    "completed",
    "failed",
    "cancelled",
)

# Forward pipeline edge: each active state has exactly one "next" state.
_FORWARD: dict[ReportStatus, ReportStatus] = {
    "draft": "searching",
    "searching": "extracting",
    "extracting": "retrieving",
    "retrieving": "generating",
    "generating": "review_1",
    "review_1": "detecting",
    "detecting": "humanizing",
    "humanizing": "translating",
    "translating": "post_translation_review",
    "post_translation_review": "converging",
    "converging": "review_2",
    "review_2": "validating",
    "validating": "completed",
}

TERMINAL_REPORT_STATUSES: frozenset[ReportStatus] = frozenset(
    {"completed", "failed", "cancelled"}
)


def _build_transition_map() -> dict[str, frozenset[ReportStatus]]:
    """Construct the full transition map.

    Policy:
      * ``draft`` -> forward (searching) | cancelled
      * any other active state -> forward | failed | cancelled
      * terminal states -> no outgoing edges
    """
    result: dict[str, frozenset[ReportStatus]] = {}

    for status in ALL_REPORT_STATUSES:
        if status in TERMINAL_REPORT_STATUSES:
            result[status] = frozenset()
            continue

        allowed: set[ReportStatus] = set()

        if status == "draft":
            allowed.add("searching")
            allowed.add("cancelled")
        else:
            next_status = _FORWARD.get(status)
            if next_status is not None:
                allowed.add(next_status)
            allowed.add("failed")
            allowed.add("cancelled")

        result[status] = frozenset(allowed)

    return result


# Keyed by ``str`` on purpose: callers obtain the status from a TEXT
# column (``reports.status``) which mypy sees as ``str``, not the
# narrow ``ReportStatus`` literal union.
ALLOWED_REPORT_TRANSITIONS: dict[str, frozenset[ReportStatus]] = (
    _build_transition_map()
)


def can_transition(from_status: str, to_status: str) -> bool:
    """Return True iff ``to_status`` is a legal next state from
    ``from_status``. Unknown statuses return False (fail-closed)."""
    allowed = ALLOWED_REPORT_TRANSITIONS.get(from_status)
    if allowed is None:
        return False
    return to_status in allowed
