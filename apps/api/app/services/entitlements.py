"""M37 — Entitlements / quota enforcement (Phase 2 MVP).

Scope:
  * resolve a workspace's live plan (via its subscription)
  * read per-feature limits from ``plan_entitlements``
  * atomic quota checks for gauge features using a
    per-(workspace, feature) PostgreSQL advisory transaction lock

Semantics:
  * ``limit_value IS NULL``  -> unlimited
  * ``limit_value = 0``      -> zero allowed
  * ``limit_value >= 1``     -> hard cap

Gauge features count the *current* total (e.g. projects.max,
members.max).  Monthly / event-based features are out of scope
for this module.
"""
from __future__ import annotations

import uuid

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.exceptions import QuotaExceeded
from app.db.models.membership import WorkspaceMembership
from app.db.models.plan import Plan, PlanEntitlement
from app.db.models.project import Project
from app.db.models.project_file import ProjectFile
from app.db.models.subscription import Subscription
from app.domain.billing import ACTIVE_SUBSCRIPTION_STATUSES
from app.domain.membership import MEMBERSHIP_ACTIVE
from app.domain.plan import (
    FEATURE_PROJECTS_MAX,
    FEATURE_REPORTS_MONTHLY,
    FEATURE_STORAGE_BYTES,
)

# --------------------------------------------------------------------------
# Plan resolution
# --------------------------------------------------------------------------

def resolve_active_plan(
    db: Session, *, workspace_id: uuid.UUID
) -> Plan | None:
    """Return the workspace's live plan, or ``None``.

    "Live" = subscription in one of ``trialing / active / past_due``.
    """
    stmt = (
        select(Plan)
        .join(Subscription, Subscription.plan_id == Plan.id)
        .where(
            Subscription.workspace_id == workspace_id,
            Subscription.status.in_(ACTIVE_SUBSCRIPTION_STATUSES),
        )
        .limit(1)
    )
    return db.execute(stmt).scalar_one_or_none()


def get_limit(
    db: Session,
    *,
    plan_id: uuid.UUID,
    feature: str,
) -> int | None:
    """Return ``plan_entitlements.limit_value`` for (plan, feature).

    ``None`` means unlimited.  Raises ``KeyError`` when the plan
    does not define the feature (treated as a programming error,
    since the DB CHECK constraint enforces a fixed feature set).
    """
    row = db.execute(
        select(PlanEntitlement).where(
            PlanEntitlement.plan_id == plan_id,
            PlanEntitlement.feature == feature,
        )
    ).scalar_one_or_none()
    if row is None:
        raise KeyError(feature)
    return row.limit_value


# --------------------------------------------------------------------------
# Gauge counters
# --------------------------------------------------------------------------

def count_active_projects(
    db: Session, *, workspace_id: uuid.UUID
) -> int:
    """Projects that count against ``projects.max``.

    Archived projects are excluded: archiving releases the slot.
    """
    return int(
        db.execute(
            select(func.count())
            .select_from(Project)
            .where(
                Project.workspace_id == workspace_id,
                Project.status != "archived",
            )
        ).scalar_one()
    )


def count_active_members(
    db: Session, *, workspace_id: uuid.UUID
) -> int:
    """Active memberships that count against ``members.max``.

    Not enforced anywhere in Phase 2 — helper exists for Phase 3.
    """
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
# Advisory lock
# --------------------------------------------------------------------------

def lock_workspace_quota(
    db: Session, *, workspace_id: uuid.UUID, feature: str
) -> None:
    """Take a per-(workspace, feature) transaction-scoped advisory lock.

    The lock is released automatically on COMMIT or ROLLBACK of the
    enclosing transaction.  Serializes concurrent quota checks for
    the same workspace+feature.
    """
    key = f"m37:quota:{feature}:{workspace_id}"
    db.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:k))"),
        {"k": key},
    )


# --------------------------------------------------------------------------
# Enforcement
# --------------------------------------------------------------------------



def count_active_storage_bytes(
    db: Session, *, workspace_id: uuid.UUID
) -> int:
    """Current bytes of active (non-deleted) project files."""
    value = db.execute(
        select(func.coalesce(func.sum(ProjectFile.size_bytes), 0))
        .join(Project, Project.id == ProjectFile.project_id)
        .where(
            Project.workspace_id == workspace_id,
            ProjectFile.deleted_at.is_(None),
        )
    ).scalar_one()
    return int(value or 0)


def check_and_reserve_storage_bytes(
    db: Session, *,
    workspace_id: uuid.UUID,
    additional_bytes: int,
) -> None:
    """Enforce the storage gauge under a workspace advisory lock.

    The caller must hold this transaction until its file row is
    committed or rolled back. Concurrent uploads are serialized by
    the same (workspace, feature) advisory lock.
    """
    if additional_bytes < 0:
        raise ValueError("additional_bytes must be >= 0")
    lock_workspace_quota(
        db,
        workspace_id=workspace_id,
        feature=FEATURE_STORAGE_BYTES,
    )
    plan = resolve_active_plan(db, workspace_id=workspace_id)
    if plan is None:
        return
    limit = get_limit(
        db,
        plan_id=plan.id,
        feature=FEATURE_STORAGE_BYTES,
    )
    if limit is None:
        return
    current = count_active_storage_bytes(
        db,
        workspace_id=workspace_id,
    )
    if current + additional_bytes > limit:
        raise QuotaExceeded(
            feature=FEATURE_STORAGE_BYTES,
            limit=limit,
            current=current,
        )


def check_and_reserve_project_slot(
    db: Session, *, workspace_id: uuid.UUID
) -> None:
    """Ensure one more project may be created for this workspace.

    MUST be called inside the same transaction that will insert the
    ``Project`` row — the advisory lock is only effective until the
    next COMMIT/ROLLBACK.  A follow-up COMMIT by ``create_project``
    closes the reservation window atomically with the INSERT.

    Raises ``QuotaExceeded`` when ``projects.max`` is reached.
    Unlimited plans (``limit_value IS NULL``) always pass.

    Fail-open when the workspace has no live subscription: the
    provisioning path (``ensure_default_workspace``) guarantees a
    subscription; a missing plan indicates a data integrity issue
    rather than a user-triggerable bypass.
    """
    lock_workspace_quota(
        db, workspace_id=workspace_id, feature=FEATURE_PROJECTS_MAX
    )
    plan = resolve_active_plan(db, workspace_id=workspace_id)
    if plan is None:
        return
    limit = get_limit(db, plan_id=plan.id, feature=FEATURE_PROJECTS_MAX)
    if limit is None:
        return
    current = count_active_projects(db, workspace_id=workspace_id)
    if current >= limit:
        raise QuotaExceeded(
            feature=FEATURE_PROJECTS_MAX,
            limit=limit,
            current=current,
        )
def check_and_reserve_reports_monthly_slot(
    db: Session, *, workspace_id: uuid.UUID
) -> None:
    """Enforce ``reports.monthly`` for the current UTC calendar month.

    Metric source: ``reports_created`` usage events
    (recorded by ``create_report``).

    MUST be called inside the same transaction that will insert the
    Report row + its usage event.  The advisory lock is held until
    COMMIT/ROLLBACK.
    """
    from app.services import usage as usage_service

    lock_workspace_quota(
        db,
        workspace_id=workspace_id,
        feature=FEATURE_REPORTS_MONTHLY,
    )
    plan = resolve_active_plan(db, workspace_id=workspace_id)
    if plan is None:
        return
    limit = get_limit(
        db, plan_id=plan.id, feature=FEATURE_REPORTS_MONTHLY
    )
    if limit is None:
        return
    current = usage_service.get_current_period_usage(
        db, workspace_id=workspace_id, metric="reports_created"
    )
    if current >= limit:
        raise QuotaExceeded(
            feature=FEATURE_REPORTS_MONTHLY,
            limit=limit,
            current=current,
        )

__all__ = [
    "check_and_reserve_project_slot",
    "check_and_reserve_reports_monthly_slot",
    "count_active_members",
    "count_active_projects",
    "count_active_storage_bytes",
    "check_and_reserve_storage_bytes",
    "get_limit",
    "lock_workspace_quota",
    "resolve_active_plan",
]
