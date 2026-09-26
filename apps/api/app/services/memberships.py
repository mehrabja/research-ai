"""M37 — Workspace membership service.

Phase 2-A1 (invitations) + Phase 2-E (role change, removal,
ownership transfer).

Role matrix (non-owner roles only):
  owner  -> may modify any non-owner member's role; may remove any
            non-owner member; may promote a member/viewer to admin;
            may transfer ownership (atomically demotes self to admin).
  admin  -> may modify member/viewer roles (not to admin); may
            remove member/viewer; cannot touch another admin or the
            owner; may downgrade/remove self.
  member -> no member-management permissions.
  viewer -> no member-management permissions.

Ownership invariants:
  * workspace.owner_user_id always matches exactly one active
    ``owner`` membership.  The DB partial unique index
    ``ux_workspace_memberships_owner_active`` is the safety net.
  * the owner's own role cannot be changed except by
    ``transfer_ownership``.
  * the owner cannot be removed; transfer first.
"""
from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import (
    InsufficientRole,
    OwnerRoleImmutable,
    QuotaExceeded,
    WorkspaceNotFound,
)
from app.db.models.membership import WorkspaceMembership
from app.db.models.workspace import Workspace
from app.domain.membership import (
    MEMBERSHIP_ACTIVE,
    MEMBERSHIP_REMOVED,
    ROLE_ADMIN,
    ROLE_MEMBER,
    ROLE_OWNER,
    ROLE_VIEWER,
    role_at_least,
)
from app.domain.plan import FEATURE_MEMBERS_MAX
from app.services import entitlements as entitlements_service
from app.services.audit import emit_audit

# Assignable via change_member_role.  Owner is reachable only via
# transfer_ownership.
_ASSIGNABLE_ROLES: frozenset[str] = frozenset(
    {ROLE_ADMIN, ROLE_MEMBER, ROLE_VIEWER}
)


# --------------------------------------------------------------------------
# Reads
# --------------------------------------------------------------------------

def get_membership(
    db: Session, *, workspace_id: uuid.UUID, user_id: uuid.UUID
) -> WorkspaceMembership | None:
    return db.execute(
        select(WorkspaceMembership).where(
            WorkspaceMembership.workspace_id == workspace_id,
            WorkspaceMembership.user_id == user_id,
        )
    ).scalar_one_or_none()


def require_active_membership(
    db: Session, *, workspace_id: uuid.UUID, user_id: uuid.UUID
) -> WorkspaceMembership:
    m = get_membership(db, workspace_id=workspace_id, user_id=user_id)
    if m is None or m.status != MEMBERSHIP_ACTIVE:
        # 404 hides workspace existence — repo convention.
        raise WorkspaceNotFound()
    return m


def require_minimum_role(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    minimum: str,
) -> WorkspaceMembership:
    m = require_active_membership(
        db, workspace_id=workspace_id, user_id=user_id
    )
    if not role_at_least(m.role, minimum):
        raise InsufficientRole()
    return m


def count_active_members(db: Session, *, workspace_id: uuid.UUID) -> int:
    return int(
        db.execute(
            select(func.count())
            .select_from(WorkspaceMembership)
            .where(
                WorkspaceMembership.workspace_id == workspace_id,
                WorkspaceMembership.status == MEMBERSHIP_ACTIVE,
            )
        ).scalar_one()
    )


# --------------------------------------------------------------------------
# Quota
# --------------------------------------------------------------------------

def ensure_member_quota(db: Session, *, workspace_id: uuid.UUID) -> None:
    """Raise QuotaExceeded if adding one more member would exceed
    ``members.max``.  Holds a per-(workspace, feature) advisory lock
    until the enclosing transaction COMMITs."""
    entitlements_service.lock_workspace_quota(
        db, workspace_id=workspace_id, feature=FEATURE_MEMBERS_MAX
    )
    plan = entitlements_service.resolve_active_plan(
        db, workspace_id=workspace_id
    )
    if plan is None:
        return
    limit = entitlements_service.get_limit(
        db, plan_id=plan.id, feature=FEATURE_MEMBERS_MAX
    )
    if limit is None:
        return
    current = count_active_members(db, workspace_id=workspace_id)
    if current >= limit:
        raise QuotaExceeded(
            feature=FEATURE_MEMBERS_MAX,
            limit=limit,
            current=current,
        )


# --------------------------------------------------------------------------
# Add / reactivate
# --------------------------------------------------------------------------

def add_or_reactivate_member(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    role: str,
) -> tuple[WorkspaceMembership, bool]:
    """Return ``(membership, created_or_reactivated)``.

    Idempotent: if an active membership already exists for
    (workspace, user), returns it unchanged with ``False``.
    Otherwise, a removed row is reactivated, or a new row is created,
    and ``True`` is returned.
    """
    existing = get_membership(
        db, workspace_id=workspace_id, user_id=user_id
    )
    if existing is not None:
        if existing.status == MEMBERSHIP_ACTIVE:
            return existing, False
        existing.status = MEMBERSHIP_ACTIVE
        existing.role = role
        db.flush()
        return existing, True

    m = WorkspaceMembership(
        workspace_id=workspace_id,
        user_id=user_id,
        role=role,
        status=MEMBERSHIP_ACTIVE,
    )
    db.add(m)
    db.flush()
    return m, True


# --------------------------------------------------------------------------
# Role change
# --------------------------------------------------------------------------

def change_member_role(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    target_user_id: uuid.UUID,
    new_role: str,
) -> WorkspaceMembership:
    """Change a member's role within the workspace.

    * ``new_role`` must be one of ``admin`` / ``member`` / ``viewer``.
      The ``owner`` role is only reachable via
      :func:`transfer_ownership`.
    * Owner may set any non-owner role on any non-owner member.
    * Admin may set ``member`` / ``viewer`` on member/viewer members,
      and may downgrade self.  Admin cannot create another admin and
      cannot touch another admin.
    * Idempotent: setting the same role returns the row unchanged.
    """
    if new_role not in _ASSIGNABLE_ROLES:
        # ``owner`` is not assignable here.
        raise OwnerRoleImmutable()

    actor = require_active_membership(
        db, workspace_id=workspace_id, user_id=actor_user_id
    )
    target = require_active_membership(
        db, workspace_id=workspace_id, user_id=target_user_id
    )

    if target.role == ROLE_OWNER:
        # Must use transfer_ownership to change the owner.
        raise OwnerRoleImmutable()

    is_self = actor_user_id == target_user_id

    if actor.role == ROLE_OWNER:
        allowed = True
    elif actor.role == ROLE_ADMIN:
        # Admin cannot touch another admin.
        if target.role == ROLE_ADMIN and not is_self or new_role == ROLE_ADMIN:
            allowed = False
        else:
            allowed = True
    else:
        allowed = False

    if not allowed:
        raise InsufficientRole()

    old_role = target.role
    if old_role == new_role:
        return target  # idempotent

    target.role = new_role
    db.flush()

    emit_audit(
        "MEMBER_ROLE_CHANGED",
        user_id=str(actor_user_id),
        workspace_id=str(workspace_id),
        membership_id=str(target.id),
        from_role=old_role,
        to_role=new_role,
    )
    return target


# --------------------------------------------------------------------------
# Removal
# --------------------------------------------------------------------------

def remove_member(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    target_user_id: uuid.UUID,
) -> WorkspaceMembership:
    """Soft-remove a member (``status = removed``).

    * Owner cannot be removed (transfer first).
    * Owner may remove any non-owner member.
    * Admin may remove member/viewer and may remove self.
    * Admin cannot remove another admin.
    * Idempotent at the caller level: re-inviting a removed user
      reactivates the same row via ``add_or_reactivate_member``.
    """
    from app.core.exceptions import LastOwner

    actor = require_active_membership(
        db, workspace_id=workspace_id, user_id=actor_user_id
    )
    target = require_active_membership(
        db, workspace_id=workspace_id, user_id=target_user_id
    )

    if target.role == ROLE_OWNER:
        # Owner must transfer ownership before leaving.
        raise LastOwner()

    is_self = actor_user_id == target_user_id

    if actor.role == ROLE_OWNER:
        allowed = True
    elif actor.role == ROLE_ADMIN:
        if is_self:
            allowed = True  # admin may leave
        elif target.role == ROLE_ADMIN:
            allowed = False  # admin cannot remove another admin
        else:
            allowed = True
    else:
        allowed = False

    if not allowed:
        raise InsufficientRole()

    if target.status == MEMBERSHIP_REMOVED:
        return target  # idempotent

    target.status = MEMBERSHIP_REMOVED
    db.flush()

    emit_audit(
        "MEMBER_REMOVED",
        user_id=str(actor_user_id),
        workspace_id=str(workspace_id),
        membership_id=str(target.id),
        reason="self" if is_self else "admin_action",
    )
    return target


# --------------------------------------------------------------------------
# Ownership transfer
# --------------------------------------------------------------------------

def transfer_ownership(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    target_user_id: uuid.UUID,
) -> Workspace:
    """Atomically transfer workspace ownership.

    Preconditions:
      * caller is the current owner
      * target is an active member
      * target != caller

    Effects (in a single transaction, holding a ``FOR UPDATE`` row
    lock on the workspace):
      * old owner's membership role -> admin
      * target's membership role   -> owner
      * ``workspace.owner_user_id`` -> target

    Ordering note
    -------------
    PostgreSQL enforces the partial unique index
    ``ux_workspace_memberships_owner_active`` per statement, so the
    old owner must lose the ``owner`` role BEFORE the target gains
    it.  A single ``db.flush()`` after both role changes would let
    SQLAlchemy batch the two UPDATEs into one ``executemany`` whose
    row order is not under our control.  We therefore flush each
    role change separately to force two sequential statements.

    Concurrent transfers (A->B and A->C) are serialized by the
    workspace row lock; exactly one succeeds.
    """
    if actor_user_id == target_user_id:
        raise InsufficientRole()

    ws = db.execute(
        select(Workspace)
        .where(Workspace.id == workspace_id)
        .with_for_update()
    ).scalar_one_or_none()
    if ws is None:
        raise WorkspaceNotFound()

    if ws.owner_user_id != actor_user_id:
        # Caller is no longer the owner (concurrent transfer already
        # landed, or caller was never owner).
        raise InsufficientRole()

    actor_m = require_active_membership(
        db, workspace_id=workspace_id, user_id=actor_user_id
    )
    if actor_m.role != ROLE_OWNER:
        raise InsufficientRole()

    target_m = require_active_membership(
        db, workspace_id=workspace_id, user_id=target_user_id
    )

    old_role = target_m.role

    # Step 1: current owner relinquishes the role FIRST.
    # This makes the partial unique index see 0 owners, which is
    # allowed (the index only enforces "at most one").
    actor_m.role = ROLE_ADMIN
    db.flush()

    # Step 2: target gains the owner role.
    target_m.role = ROLE_OWNER
    db.flush()

    # Step 3: update the workspace pointer.
    ws.owner_user_id = target_user_id
    db.flush()

    emit_audit(
        "OWNERSHIP_TRANSFERRED",
        user_id=str(actor_user_id),
        workspace_id=str(workspace_id),
        membership_id=str(target_m.id),
        from_role=old_role,
        to_role=ROLE_OWNER,
    )
    return ws


__all__ = [
    "add_or_reactivate_member",
    "change_member_role",
    "count_active_members",
    "ensure_member_quota",
    "get_membership",
    "remove_member",
    "require_active_membership",
    "require_minimum_role",
    "transfer_ownership",
]
