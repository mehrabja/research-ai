"""M34 — Project membership management."""
from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import (
    CollaborationConfigurationInvalid,
    CollaborationInvalid,
    CollaborationMemberConflict,
    CollaborationNotFound,
)
from app.db.models.collaboration import ProjectMember
from app.db.models.project import Project
from app.db.models.user import User
from app.domain.collaboration import PROJECT_ROLES, ProjectRole
from app.services.collaboration import events as events_svc
from app.services.collaboration import permissions as perms


def _assert_user_exists(
    db: Session, *, user_id: uuid.UUID,
) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise CollaborationNotFound()
    return user


def _assert_no_owner_row(
    db: Session, *, project_id: uuid.UUID, user_id: uuid.UUID,
) -> None:
    project = db.get(Project, project_id)
    if project is None:
        raise CollaborationNotFound()
    if project.user_id == user_id:
        raise CollaborationInvalid(
            "project owner does not need a member row"
        )


def add_member(
    db: Session,
    *,
    actor_user_id: uuid.UUID,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    role: str,
) -> ProjectMember:
    settings = get_settings()
    if not settings.collaboration_enabled:
        raise CollaborationConfigurationInvalid(
            "collaboration is disabled"
        )
    perms.require_manage(
        db, project_id=project_id, user_id=actor_user_id,
    )
    if role not in PROJECT_ROLES:
        raise CollaborationInvalid(f"unknown role: {role}")
    if role == ProjectRole.OWNER.value:
        raise CollaborationInvalid(
            "ownership transfer is not supported via member row"
        )
    _assert_user_exists(db, user_id=user_id)
    _assert_no_owner_row(
        db, project_id=project_id, user_id=user_id,
    )

    existing = db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise CollaborationMemberConflict(
            "user is already a project member"
        )

    count = int(db.execute(
        select(func.count()).select_from(ProjectMember).where(
            ProjectMember.project_id == project_id
        )
    ).scalar_one())
    if count >= int(
        settings.collaboration_max_members_per_project
    ):
        raise CollaborationInvalid("project member limit reached")

    member = ProjectMember(
        project_id=project_id,
        user_id=user_id,
        role=role,
        added_by=actor_user_id,
    )
    db.add(member)
    db.flush()
    events_svc.emit_event(
        db,
        project_id=project_id,
        actor_user_id=actor_user_id,
        event_type="member_added",
        target_type="project_member",
        target_id=member.id,
        metadata={"user_id": str(user_id), "role": role},
    )
    return member


def remove_member(
    db: Session,
    *,
    actor_user_id: uuid.UUID,
    project_id: uuid.UUID,
    member_id: uuid.UUID,
) -> None:
    perms.require_manage(
        db, project_id=project_id, user_id=actor_user_id,
    )
    member = db.get(ProjectMember, member_id)
    if member is None or member.project_id != project_id:
        raise CollaborationNotFound()

    removed_user_id = member.user_id
    db.delete(member)
    events_svc.emit_event(
        db,
        project_id=project_id,
        actor_user_id=actor_user_id,
        event_type="member_removed",
        target_type="project_member",
        target_id=member_id,
        metadata={"user_id": str(removed_user_id)},
    )


def change_role(
    db: Session,
    *,
    actor_user_id: uuid.UUID,
    project_id: uuid.UUID,
    member_id: uuid.UUID,
    new_role: str,
) -> ProjectMember:
    perms.require_manage(
        db, project_id=project_id, user_id=actor_user_id,
    )
    if new_role not in PROJECT_ROLES:
        raise CollaborationInvalid(f"unknown role: {new_role}")
    if new_role == ProjectRole.OWNER.value:
        raise CollaborationInvalid(
            "ownership transfer is not supported via role change"
        )
    member = db.get(ProjectMember, member_id)
    if member is None or member.project_id != project_id:
        raise CollaborationNotFound()

    old_role = member.role
    member.role = new_role
    db.flush()
    events_svc.emit_event(
        db,
        project_id=project_id,
        actor_user_id=actor_user_id,
        event_type="role_changed",
        target_type="project_member",
        target_id=member_id,
        metadata={"old_role": old_role, "new_role": new_role},
    )
    return member


def list_members(
    db: Session,
    *,
    actor_user_id: uuid.UUID,
    project_id: uuid.UUID,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[ProjectMember], int]:
    perms.require_read(
        db, project_id=project_id, user_id=actor_user_id,
    )
    base = select(ProjectMember).where(
        ProjectMember.project_id == project_id
    )
    total = int(db.execute(
        select(func.count()).select_from(base.subquery())
    ).scalar_one())
    rows = list(db.execute(
        base.order_by(
            ProjectMember.created_at.asc(),
            ProjectMember.id.asc(),
        ).limit(limit).offset(offset)
    ).scalars().all())
    return rows, total


__all__ = [
    "add_member",
    "remove_member",
    "change_role",
    "list_members",
]
