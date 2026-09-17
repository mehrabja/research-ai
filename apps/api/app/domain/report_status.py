"""Report status: canonical type and state machine."""
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
    "pre_translation_review",
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
    "pre_translation_review",
    "translating",
    "post_translation_review",
    "converging",
    "review_2",
    "validating",
    "completed",
    "failed",
    "cancelled",
)

_FORWARD: dict[ReportStatus, ReportStatus] = {
    "draft": "searching",
    "searching": "extracting",
    "extracting": "retrieving",
    "retrieving": "generating",
    "generating": "review_1",
    "review_1": "detecting",
    "detecting": "humanizing",
    "humanizing": "pre_translation_review",
    "pre_translation_review": "translating",
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
    result: dict[str, frozenset[ReportStatus]] = {}

    for status in ALL_REPORT_STATUSES:
        if status in TERMINAL_REPORT_STATUSES:
            result[status] = frozenset()
            continue

        allowed: set[ReportStatus] = set()

        if status == "draft":
            allowed.add("searching")
            allowed.add("generating")
            allowed.add("cancelled")
        else:
            next_status = _FORWARD.get(status)
            if next_status is not None:
                allowed.add(next_status)
            allowed.add("failed")
            allowed.add("cancelled")

        result[status] = frozenset(allowed)

    return result


ALLOWED_REPORT_TRANSITIONS: dict[str, frozenset[ReportStatus]] = (
    _build_transition_map()
)


def can_transition(from_status: str, to_status: str) -> bool:
    allowed = ALLOWED_REPORT_TRANSITIONS.get(from_status)
    if allowed is None:
        return False
    return to_status in allowed
