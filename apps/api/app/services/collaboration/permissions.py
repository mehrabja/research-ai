"""M34 — Explicit project permission resolution.

Ownership is derived from projects.user_id. Everyone else must have a
ProjectMember row with a role that grants the requested permission.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import (
    CollaborationForbidden,
    CollaborationNotFound,
)
from app.db.models.collaboration import ProjectMember
from app.db.models.project import Project
from app.domain.collaboration import (
    ProjectRole,
    can_comment,
    can_manage,
    can_read,
    can_review,
    can_write,
)


def _load_project(db: Session, *, project_id: uuid.UUID) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise CollaborationNotFound()
    return project


def _member_row(
    db: Session, *, project_id: uuid.UUID, user_id: uuid.UUID,
) -> ProjectMember | None:
    return db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
        )
    ).scalar_one_or_none()


def resolve_role(
    db: Session, *, project_id: uuid.UUID, user_id: uuid.UUID,
) -> str | None:
    """Return the effective role for a user, or None if no access."""
    project = _load_project(db, project_id=project_id)
    if project.user_id == user_id:
        return ProjectRole.OWNER.value
    member = _member_row(
        db, project_id=project_id, user_id=user_id,
    )
    if member is None:
        return None
    return member.role


def require_role_or_owner(
    db: Session, *, project_id: uuid.UUID, user_id: uuid.UUID,
) -> str:
    role = resolve_role(
        db, project_id=project_id, user_id=user_id,
    )
    if role is None:
        raise CollaborationNotFound()
    return role


def require_read(
    db: Session, *, project_id: uuid.UUID, user_id: uuid.UUID,
) -> str:
    role = require_role_or_owner(
        db, project_id=project_id, user_id=user_id,
    )
    if not can_read(role):
        raise CollaborationForbidden()
    return role


def require_write(
    db: Session, *, project_id: uuid.UUID, user_id: uuid.UUID,
) -> str:
    role = require_role_or_owner(
        db, project_id=project_id, user_id=user_id,
    )
    if not can_write(role):
        raise CollaborationForbidden()
    return role


def require_comment(
    db: Session, *, project_id: uuid.UUID, user_id: uuid.UUID,
) -> str:
    role = require_role_or_owner(
        db, project_id=project_id, user_id=user_id,
    )
    if not can_comment(role):
        raise CollaborationForbidden()
    return role


def require_review(
    db: Session, *, project_id: uuid.UUID, user_id: uuid.UUID,
) -> str:
    role = require_role_or_owner(
        db, project_id=project_id, user_id=user_id,
    )
    if not can_review(role):
        raise CollaborationForbidden()
    return role


def require_manage(
    db: Session, *, project_id: uuid.UUID, user_id: uuid.UUID,
) -> str:
    role = require_role_or_owner(
        db, project_id=project_id, user_id=user_id,
    )
    if not can_manage(role):
        raise CollaborationForbidden()
    return role


__all__ = [
    "resolve_role",
    "require_role_or_owner",
    "require_read",
    "require_write",
    "require_comment",
    "require_review",
    "require_manage",
]
