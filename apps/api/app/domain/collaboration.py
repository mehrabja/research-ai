"""M34 — Collaboration / versioning / review workspace domain primitives."""
from __future__ import annotations

from enum import StrEnum

M34_VERSION = "m34.1"


class ProjectRole(StrEnum):
    OWNER = "owner"
    EDITOR = "editor"
    REVIEWER = "reviewer"
    VIEWER = "viewer"


class CommentStatus(StrEnum):
    OPEN = "open"
    RESOLVED = "resolved"
    REOPENED = "reopened"


class ReviewTaskStatus(StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    RESOLVED = "resolved"
    REJECTED = "rejected"


class ReviewSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    BLOCKING = "blocking"


class CollaborationEventType(StrEnum):
    MEMBER_ADDED = "member_added"
    MEMBER_REMOVED = "member_removed"
    ROLE_CHANGED = "role_changed"
    VERSION_CREATED = "version_created"
    BRANCH_CREATED = "branch_created"
    BRANCH_MERGED = "branch_merged"
    COMMENT_CREATED = "comment_created"
    COMMENT_RESOLVED = "comment_resolved"
    COMMENT_REOPENED = "comment_reopened"
    REVIEW_TASK_CREATED = "review_task_created"
    REVIEW_TASK_STATUS_CHANGED = "review_task_status_changed"
    REVIEW_TASK_RESOLVED = "review_task_resolved"


PROJECT_ROLES = tuple(r.value for r in ProjectRole)
COMMENT_STATUSES = tuple(s.value for s in CommentStatus)
REVIEW_TASK_STATUSES = tuple(s.value for s in ReviewTaskStatus)
REVIEW_SEVERITIES = tuple(s.value for s in ReviewSeverity)
COLLABORATION_EVENT_TYPES = tuple(
    e.value for e in CollaborationEventType
)

# Deterministic permission matrix.
#   read    → can list/read versions, comments, reviews
#   write   → can create versions/branches, run generation
#   comment → can create comments
#   review  → can create/complete review tasks
#   manage  → can add/remove members, change roles, force-finalize
_ROLE_PERMISSIONS: dict[str, set[str]] = {
    ProjectRole.OWNER.value: {
        "read", "write", "comment", "review", "manage",
    },
    ProjectRole.EDITOR.value: {
        "read", "write", "comment", "review",
    },
    ProjectRole.REVIEWER.value: {
        "read", "comment", "review",
    },
    ProjectRole.VIEWER.value: {
        "read",
    },
}


def role_has(role: str, permission: str) -> bool:
    return permission in _ROLE_PERMISSIONS.get(role, set())


def can_read(role: str) -> bool:
    return role_has(role, "read")


def can_write(role: str) -> bool:
    return role_has(role, "write")


def can_comment(role: str) -> bool:
    return role_has(role, "comment")


def can_review(role: str) -> bool:
    return role_has(role, "review")


def can_manage(role: str) -> bool:
    return role_has(role, "manage")


__all__ = [
    "M34_VERSION",
    "ProjectRole",
    "CommentStatus",
    "ReviewTaskStatus",
    "ReviewSeverity",
    "CollaborationEventType",
    "PROJECT_ROLES",
    "COMMENT_STATUSES",
    "REVIEW_TASK_STATUSES",
    "REVIEW_SEVERITIES",
    "COLLABORATION_EVENT_TYPES",
    "role_has",
    "can_read",
    "can_write",
    "can_comment",
    "can_review",
    "can_manage",
]
