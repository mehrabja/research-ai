"""M37 — Workspace service.

Phase 1 (tenant foundation):
  * ``get_default_workspace_for_user`` — deterministic lookup
  * ``ensure_default_workspace``       — lazy provisioning with
                                          per-user advisory lock
Phase 2-D (explicit CRUD):
  * ``create_workspace``
  * ``list_workspaces_for_user``
  * ``get_workspace_for_user``
  * ``update_workspace``
"""
from __future__ import annotations

import secrets
import uuid
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.exceptions import (
    AppError,
    InsufficientRole,
    WorkspaceNotFound,
)
from app.db.models.membership import WorkspaceMembership
from app.db.models.plan import Plan
from app.db.models.subscription import Subscription
from app.db.models.user import User
from app.db.models.workspace import Workspace
from app.domain.billing import PROVIDER_NONE, SUB_ACTIVE
from app.domain.membership import (
    MEMBERSHIP_ACTIVE,
    ROLE_ADMIN,
    ROLE_OWNER,
    role_at_least,
)
from app.domain.plan import DEFAULT_PLAN_CODE
from app.domain.workspace import (
    WORKSPACE_READABLE_STATUSES,
    WORKSPACE_STATUS_ACTIVE,
    slugify,
)

# --------------------------------------------------------------------------
# Phase 1 — default (personal) workspace
# --------------------------------------------------------------------------

def get_default_workspace_for_user(
    db: Session, *, user_id: uuid.UUID
) -> Workspace | None:
    """Return the earliest active workspace the user owns.

    Deterministic ordering: ``created_at ASC, id ASC``.
    Returns ``None`` when the user has no owned workspace.
    """
    stmt = (
        select(Workspace)
        .join(
            WorkspaceMembership,
            WorkspaceMembership.workspace_id == Workspace.id,
        )
        .where(
            WorkspaceMembership.user_id == user_id,
            WorkspaceMembership.role == ROLE_OWNER,
            WorkspaceMembership.status == MEMBERSHIP_ACTIVE,
            Workspace.status == WORKSPACE_STATUS_ACTIVE,
        )
        .order_by(Workspace.created_at.asc(), Workspace.id.asc())
        .limit(1)
    )
    return db.execute(stmt).scalar_one_or_none()


def ensure_default_workspace(
    db: Session, *, user_id: uuid.UUID
) -> Workspace:
    """Return the user's personal workspace, provisioning on demand.

    Concurrency-safe: takes a per-user ``pg_advisory_xact_lock``
    before inserting, then re-checks. Two simultaneous callers
    cannot both create a personal workspace for the same user.
    """
    ws = get_default_workspace_for_user(db, user_id=user_id)
    if ws is not None:
        return ws

    # Serialize concurrent provisioning for this user.
    db.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:k))"),
        {"k": f"m37:default_workspace:{user_id}"},
    )

    ws = get_default_workspace_for_user(db, user_id=user_id)
    if ws is not None:
        return ws

    user = db.get(User, user_id)
    if user is None:
        raise RuntimeError(
            f"M37: cannot provision workspace for unknown user {user_id}"
        )

    local = "user"
    if user.email:
        local = user.email.split("@", 1)[0].strip() or "user"

    slug = _allocate_slug(db, local)
    workspace = Workspace(
        name=f"{local}'s workspace"[:120],
        slug=slug,
        owner_user_id=user_id,
        status=WORKSPACE_STATUS_ACTIVE,
    )
    db.add(workspace)
    db.flush()

    db.add(
        WorkspaceMembership(
            workspace_id=workspace.id,
            user_id=user_id,
            role=ROLE_OWNER,
            status=MEMBERSHIP_ACTIVE,
        )
    )

    free_plan = db.execute(
        select(Plan).where(Plan.code == DEFAULT_PLAN_CODE)
    ).scalar_one_or_none()
    if free_plan is None:
        raise RuntimeError(
            f"M37: default plan {DEFAULT_PLAN_CODE!r} is missing; "
            "ensure migration 0032 has been applied."
        )

    db.add(
        Subscription(
            workspace_id=workspace.id,
            plan_id=free_plan.id,
            status=SUB_ACTIVE,
            provider=PROVIDER_NONE,
        )
    )
    db.flush()
    return workspace


def _allocate_slug(db: Session, base: str) -> str:
    """Return a slug not yet present in ``workspaces``.

    First attempt uses the deterministic base slug. On collision,
    appends a short random suffix and retries (bounded).
    """
    base_slug = slugify(base)
    candidate = base_slug
    for _ in range(64):
        exists = db.execute(
            text("SELECT 1 FROM workspaces WHERE slug = :s LIMIT 1"),
            {"s": candidate},
        ).first()
        if exists is None:
            return candidate
        candidate = f"{base_slug[:48]}-{secrets.token_hex(3)}"
    raise RuntimeError(
        f"M37: could not allocate workspace slug from {base!r}"
    )


# --------------------------------------------------------------------------
# Phase 2-D — explicit workspace CRUD
# --------------------------------------------------------------------------

def create_workspace(
    db: Session,
    *,
    name: str,
    owner_user_id: uuid.UUID,
) -> Workspace:
    """Create a workspace with owner membership + free subscription.

    Transactional: a failure in any of the three inserts rolls all
    of them back.  Caller is responsible for COMMIT.
    """
    slug = _allocate_slug(db, name or "workspace")
    ws = Workspace(
        name=(name or "workspace")[:120],
        slug=slug,
        owner_user_id=owner_user_id,
        status=WORKSPACE_STATUS_ACTIVE,
    )
    db.add(ws)
    db.flush()

    db.add(
        WorkspaceMembership(
            workspace_id=ws.id,
            user_id=owner_user_id,
            role=ROLE_OWNER,
            status=MEMBERSHIP_ACTIVE,
        )
    )

    free = db.execute(
        select(Plan).where(Plan.code == DEFAULT_PLAN_CODE)
    ).scalar_one_or_none()
    if free is None:
        raise RuntimeError(
            f"M37: default plan {DEFAULT_PLAN_CODE!r} is missing"
        )

    db.add(
        Subscription(
            workspace_id=ws.id,
            plan_id=free.id,
            status=SUB_ACTIVE,
            provider=PROVIDER_NONE,
        )
    )
    db.flush()
    return ws


def list_workspaces_for_user(
    db: Session, *, user_id: uuid.UUID
) -> list[tuple[Workspace, str]]:
    """Return ``[(workspace, role), ...]`` for active memberships.

    Excludes ``deleted`` workspaces.  Suspended workspaces are
    listed (they are readable).
    """
    stmt = (
        select(Workspace, WorkspaceMembership.role)
        .join(
            WorkspaceMembership,
            WorkspaceMembership.workspace_id == Workspace.id,
        )
        .where(
            WorkspaceMembership.user_id == user_id,
            WorkspaceMembership.status == MEMBERSHIP_ACTIVE,
            Workspace.status.in_(WORKSPACE_READABLE_STATUSES),
        )
        .order_by(Workspace.created_at.desc(), Workspace.id.asc())
    )
    return [(w, r) for w, r in db.execute(stmt).all()]


def get_workspace_for_user(
    db: Session, *, workspace_id: uuid.UUID, user_id: uuid.UUID
) -> tuple[Workspace, str]:
    """Return ``(workspace, role)`` or raise ``WorkspaceNotFound``.

    Membership is the authorization boundary: a non-member sees 404.
    """
    stmt = (
        select(Workspace, WorkspaceMembership.role)
        .join(
            WorkspaceMembership,
            WorkspaceMembership.workspace_id == Workspace.id,
        )
        .where(
            Workspace.id == workspace_id,
            WorkspaceMembership.user_id == user_id,
            WorkspaceMembership.status == MEMBERSHIP_ACTIVE,
            Workspace.status.in_(WORKSPACE_READABLE_STATUSES),
        )
    )
    row = db.execute(stmt).first()
    if row is None:
        raise WorkspaceNotFound()
    return row[0], row[1]


def update_workspace(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    name: str | None = None,
    settings: dict[str, Any] | None = None,
) -> Workspace:
    """Owner/admin can update name and settings.

    Suspended or deleted workspaces cannot be updated.
    """
    ws, role = get_workspace_for_user(
        db, workspace_id=workspace_id, user_id=actor_user_id
    )
    if ws.status != WORKSPACE_STATUS_ACTIVE:
        raise InsufficientRole()
    if not role_at_least(role, ROLE_ADMIN):
        raise InsufficientRole()

    if name is not None:
        if not name.strip():
            raise AppError("name must not be empty")
        ws.name = name.strip()[:120]
    if settings is not None:
        ws.settings = settings
    db.flush()
    return ws


__all__ = [
    "create_workspace",
    "ensure_default_workspace",
    "get_default_workspace_for_user",
    "get_workspace_for_user",
    "list_workspaces_for_user",
    "update_workspace",
]
