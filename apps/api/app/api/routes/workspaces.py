"""M37 Phase 2-D — workspace / member / invitation / usage / plan /
subscription routes."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.models.membership import WorkspaceMembership
from app.db.models.plan import Plan, PlanEntitlement
from app.db.models.user import User
from app.db.session import get_db
from app.domain.invitation import compute_state
from app.domain.plan import (
    FEATURE_AI_GENERATION_UNITS,
    FEATURE_MEMBERS_MAX,
    FEATURE_PROJECTS_MAX,
    FEATURE_REPORTS_MONTHLY,
    FEATURE_SEARCH_REQUESTS,
    FEATURE_STORAGE_BYTES,
    UNIT_FOR_FEATURE,
)
from app.schemas.invitation import (
    InvitationCreate,
    InvitationCreated,
    InvitationRead,
    MemberListResponse,
    MemberRead,
    MemberRoleUpdate,
)
from app.schemas.plan import EntitlementRead, PlanRead
from app.schemas.subscription import SubscriptionRead
from app.schemas.usage import UsageItem, UsageResponse
from app.schemas.workspace import (
    WorkspaceCreate,
    WorkspaceListItem,
    WorkspaceListResponse,
    WorkspaceRead,
    WorkspaceUpdate,
)
from app.services import billing as billing_service
from app.services import entitlements as entitlements_service
from app.services import invitations as invitations_service
from app.services import memberships as memberships_service
from app.services import usage as usage_service
from app.services import workspaces as workspaces_service

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


# ---------------------------------------------------------------------------
# Workspace CRUD
# ---------------------------------------------------------------------------

@router.post(
    "", response_model=WorkspaceRead,
    status_code=status.HTTP_201_CREATED,
)
def create_workspace(
    body: WorkspaceCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WorkspaceRead:
    ws = workspaces_service.create_workspace(
        db, name=body.name, owner_user_id=current_user.id
    )
    db.commit()
    db.refresh(ws)
    return WorkspaceRead.model_validate(ws)


@router.get("", response_model=WorkspaceListResponse)
def list_workspaces(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WorkspaceListResponse:
    rows = workspaces_service.list_workspaces_for_user(
        db, user_id=current_user.id
    )
    items = [
        WorkspaceListItem(
            id=w.id, name=w.name, slug=w.slug,
            status=w.status, role=r,
        )
        for w, r in rows
    ]
    return WorkspaceListResponse(items=items, total=len(items))


@router.get("/{workspace_id}", response_model=WorkspaceRead)
def get_workspace(
    workspace_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WorkspaceRead:
    ws, _role = workspaces_service.get_workspace_for_user(
        db, workspace_id=workspace_id, user_id=current_user.id
    )
    return WorkspaceRead.model_validate(ws)


@router.patch("/{workspace_id}", response_model=WorkspaceRead)
def patch_workspace(
    workspace_id: uuid.UUID,
    body: WorkspaceUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WorkspaceRead:
    payload = body.model_dump(exclude_unset=True)
    ws = workspaces_service.update_workspace(
        db,
        workspace_id=workspace_id,
        actor_user_id=current_user.id,
        name=payload.get("name"),
        settings=payload.get("settings"),
    )
    db.commit()
    db.refresh(ws)
    return WorkspaceRead.model_validate(ws)


# ---------------------------------------------------------------------------
# Members
# ---------------------------------------------------------------------------

@router.get(
    "/{workspace_id}/members",
    response_model=MemberListResponse,
)
def list_members(
    workspace_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MemberListResponse:
    memberships_service.require_active_membership(
        db, workspace_id=workspace_id, user_id=current_user.id
    )
    rows = list(
        db.execute(
            select(WorkspaceMembership).where(
                WorkspaceMembership.workspace_id == workspace_id,
                WorkspaceMembership.status == "active",
            )
        ).scalars()
    )
    items = [
        MemberRead(
            id=m.id, user_id=m.user_id, role=m.role,
            status=m.status, created_at=m.created_at,
        )
        for m in rows
    ]
    return MemberListResponse(items=items, total=len(items))


@router.patch(
    "/{workspace_id}/members/{user_id}",
    response_model=MemberRead,
)
def change_role(
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    body: MemberRoleUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MemberRead:
    m = memberships_service.change_member_role(
        db,
        workspace_id=workspace_id,
        actor_user_id=current_user.id,
        target_user_id=user_id,
        new_role=body.role,
    )
    db.commit()
    db.refresh(m)
    return MemberRead(
        id=m.id, user_id=m.user_id, role=m.role,
        status=m.status, created_at=m.created_at,
    )


@router.delete(
    "/{workspace_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_member(
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    memberships_service.remove_member(
        db,
        workspace_id=workspace_id,
        actor_user_id=current_user.id,
        target_user_id=user_id,
    )
    db.commit()


# ---------------------------------------------------------------------------
# Invitations
# ---------------------------------------------------------------------------

@router.post(
    "/{workspace_id}/members/invitations",
    response_model=InvitationCreated,
    status_code=status.HTTP_201_CREATED,
)
def create_invitation(
    workspace_id: uuid.UUID,
    body: InvitationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> InvitationCreated:
    inv, raw = invitations_service.create_invitation(
        db,
        workspace_id=workspace_id,
        email=body.email,
        role=body.role,
        invited_by_user_id=current_user.id,
        ttl_days=body.ttl_days,
    )
    db.commit()
    db.refresh(inv)
    state = compute_state(
        accepted_at=inv.accepted_at,
        revoked_at=inv.revoked_at,
        expires_at=inv.expires_at,
    )
    return InvitationCreated(
        invitation=InvitationRead(
            id=inv.id, workspace_id=inv.workspace_id,
            email=inv.email, role=inv.role, state=state,
            expires_at=inv.expires_at,
            accepted_at=inv.accepted_at,
            revoked_at=inv.revoked_at,
            created_at=inv.created_at,
        ),
        token=raw,
    )


# ---------------------------------------------------------------------------
# Usage / plan / subscription
# ---------------------------------------------------------------------------

def _current_usage_for_feature(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    feature: str,
    period_start,
    period_end,
) -> int:
    """Resolve current usage for a single feature.

    * gauge features (projects.max, members.max, storage.bytes) use
      a direct count (no event history)
    * monthly features (reports.monthly, ai_generation_units,
      search.requests) aggregate ``usage_events`` over the period
    """
    if feature == FEATURE_PROJECTS_MAX:
        return entitlements_service.count_active_projects(
            db, workspace_id=workspace_id
        )
    if feature == FEATURE_MEMBERS_MAX:
        return entitlements_service.count_active_members(
            db, workspace_id=workspace_id
        )
    if feature == FEATURE_STORAGE_BYTES:
        # Storage aggregation is not wired in M37.
        return 0
    if feature == FEATURE_REPORTS_MONTHLY:
        return usage_service.get_period_usage(
            db,
            workspace_id=workspace_id,
            metric="reports_created",
            period_start=period_start,
            period_end=period_end,
        )
    if feature == FEATURE_AI_GENERATION_UNITS:
        return usage_service.get_period_usage(
            db,
            workspace_id=workspace_id,
            metric="ai_generation_units",
            period_start=period_start,
            period_end=period_end,
        )
    if feature == FEATURE_SEARCH_REQUESTS:
        return usage_service.get_period_usage(
            db,
            workspace_id=workspace_id,
            metric="search_requests",
            period_start=period_start,
            period_end=period_end,
        )
    return 0


@router.get("/{workspace_id}/usage", response_model=UsageResponse)
def get_usage(
    workspace_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UsageResponse:
    memberships_service.require_active_membership(
        db, workspace_id=workspace_id, user_id=current_user.id
    )
    start, end = usage_service.period_bounds_utc()
    plan = entitlements_service.resolve_active_plan(
        db, workspace_id=workspace_id
    )
    items: list[UsageItem] = []
    if plan is not None:
        ents = list(
            db.execute(
                select(PlanEntitlement).where(
                    PlanEntitlement.plan_id == plan.id
                )
            ).scalars()
        )
        for ent in ents:
            current = _current_usage_for_feature(
                db,
                workspace_id=workspace_id,
                feature=ent.feature,
                period_start=start,
                period_end=end,
            )
            items.append(
                UsageItem(
                    metric=ent.feature,
                    current=current,
                    limit=ent.limit_value,
                    unit=UNIT_FOR_FEATURE.get(ent.feature, "count"),
                )
            )
    return UsageResponse(
        workspace_id=workspace_id,
        period_start=start,
        period_end=end,
        items=items,
    )


@router.get("/{workspace_id}/plan", response_model=PlanRead)
def get_plan(
    workspace_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PlanRead:
    memberships_service.require_active_membership(
        db, workspace_id=workspace_id, user_id=current_user.id
    )
    plan = entitlements_service.resolve_active_plan(
        db, workspace_id=workspace_id
    )
    if plan is None:
        raise billing_service.SubscriptionNotFound()
    ents = list(
        db.execute(
            select(PlanEntitlement).where(
                PlanEntitlement.plan_id == plan.id
            )
        ).scalars()
    )
    return PlanRead(
        id=plan.id, code=plan.code, name=plan.name,
        description=plan.description, status=plan.status,
        entitlements=[
            EntitlementRead(
                feature=e.feature, limit_value=e.limit_value, unit=e.unit,
            )
            for e in ents
        ],
    )


@router.get(
    "/{workspace_id}/subscription",
    response_model=SubscriptionRead,
)
def get_subscription(
    workspace_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SubscriptionRead:
    memberships_service.require_active_membership(
        db, workspace_id=workspace_id, user_id=current_user.id
    )
    sub = billing_service.require_live_subscription(
        db, workspace_id=workspace_id
    )
    plan = db.get(Plan, sub.plan_id)
    return SubscriptionRead(
        id=sub.id,
        workspace_id=sub.workspace_id,
        plan_id=sub.plan_id,
        plan_code=plan.code if plan else "",
        status=sub.status,
        current_period_start=sub.current_period_start,
        current_period_end=sub.current_period_end,
        provider=sub.provider,
        cancel_at_period_end=sub.cancel_at_period_end,
        created_at=sub.created_at,
    )
