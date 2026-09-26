"""M34 — domain primitives."""
from __future__ import annotations

from app.domain.collaboration import (
    COLLABORATION_EVENT_TYPES,
    COMMENT_STATUSES,
    M34_VERSION,
    PROJECT_ROLES,
    REVIEW_TASK_STATUSES,
    ProjectRole,
    can_comment,
    can_manage,
    can_read,
    can_review,
    can_write,
    role_has,
)


def test_version() -> None:
    assert M34_VERSION == "m34.1"


def test_roles() -> None:
    assert set(PROJECT_ROLES) == {
        "owner", "editor", "reviewer", "viewer",
    }


def test_comment_statuses() -> None:
    assert "open" in COMMENT_STATUSES
    assert "resolved" in COMMENT_STATUSES
    assert "reopened" in COMMENT_STATUSES


def test_review_task_statuses() -> None:
    required = {"open", "in_progress", "blocked", "resolved", "rejected"}
    assert required.issubset(set(REVIEW_TASK_STATUSES))


def test_event_types_cover_required() -> None:
    required = {
        "member_added", "member_removed", "role_changed",
        "version_created", "branch_created", "branch_merged",
        "comment_created", "comment_resolved", "comment_reopened",
        "review_task_created", "review_task_status_changed",
        "review_task_resolved",
    }
    assert required.issubset(set(COLLABORATION_EVENT_TYPES))


def test_owner_can_everything() -> None:
    r = ProjectRole.OWNER.value
    assert can_read(r)
    assert can_write(r)
    assert can_comment(r)
    assert can_review(r)
    assert can_manage(r)


def test_viewer_is_readonly() -> None:
    r = ProjectRole.VIEWER.value
    assert can_read(r)
    assert not can_write(r)
    assert not can_comment(r)
    assert not can_review(r)
    assert not can_manage(r)


def test_reviewer_can_review_and_comment_only() -> None:
    r = ProjectRole.REVIEWER.value
    assert can_read(r)
    assert not can_write(r)
    assert can_comment(r)
    assert can_review(r)
    assert not can_manage(r)


def test_editor_can_write_and_review() -> None:
    r = ProjectRole.EDITOR.value
    assert can_read(r)
    assert can_write(r)
    assert can_comment(r)
    assert can_review(r)
    assert not can_manage(r)


def test_unknown_role_has_no_permissions() -> None:
    for perm in ("read", "write", "comment", "review", "manage"):
        assert not role_has("bogus", perm)
