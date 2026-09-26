"""M34 — Collaboration / versioning / review API routes."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.collaboration import (
    BranchCreateRequest,
    BranchMergeRequest,
    CommentCreateRequest,
    ManuscriptBranchListResponse,
    ManuscriptBranchRead,
    ManuscriptCommentListResponse,
    ManuscriptCommentRead,
    ManuscriptReviewTaskListResponse,
    ManuscriptReviewTaskRead,
    ManuscriptVersionListResponse,
    ManuscriptVersionRead,
    MemberAddRequest,
    MemberChangeRoleRequest,
    ProjectMemberListResponse,
    ProjectMemberRead,
    ReviewTaskCreateRequest,
    ReviewTaskStatusChangeRequest,
)
from app.services.collaboration import branches as branches_svc
from app.services.collaboration import comments as comments_svc
from app.services.collaboration import membership as membership_svc
from app.services.collaboration import merge as merge_svc
from app.services.collaboration import permissions as perms
from app.services.collaboration import reviews as reviews_svc
from app.services.collaboration import versions as versions_svc
from app.services.projects import get_project

router = APIRouter(tags=["collaboration"])


# ---------------------------------------------------------------------------
# Members
# ---------------------------------------------------------------------------


@router.get(
    "/projects/{project_id}/members",
    response_model=ProjectMemberListResponse,
)
def list_members(
    project_id: uuid.UUID,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectMemberListResponse:
    rows, total = membership_svc.list_members(
        db,
        actor_user_id=current_user.id,
        project_id=project_id,
        limit=limit,
        offset=offset,
    )
    return ProjectMemberListResponse(
        items=[ProjectMemberRead.model_validate(r) for r in rows],
        total=total, limit=limit, offset=offset,
    )


@router.post(
    "/projects/{project_id}/members",
    response_model=ProjectMemberRead,
)
def add_member(
    project_id: uuid.UUID,
    body: MemberAddRequest,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectMemberRead:
    member = membership_svc.add_member(
        db,
        actor_user_id=current_user.id,
        project_id=project_id,
        user_id=body.user_id,
        role=body.role,
    )
    db.commit()
    db.refresh(member)
    response.status_code = 201
    return ProjectMemberRead.model_validate(member)


@router.patch(
    "/projects/{project_id}/members/{member_id}",
    response_model=ProjectMemberRead,
)
def change_member_role(
    project_id: uuid.UUID,
    member_id: uuid.UUID,
    body: MemberChangeRoleRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectMemberRead:
    member = membership_svc.change_role(
        db,
        actor_user_id=current_user.id,
        project_id=project_id,
        member_id=member_id,
        new_role=body.role,
    )
    db.commit()
    db.refresh(member)
    return ProjectMemberRead.model_validate(member)


@router.delete(
    "/projects/{project_id}/members/{member_id}",
    status_code=204,
)
def remove_member(
    project_id: uuid.UUID,
    member_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    membership_svc.remove_member(
        db,
        actor_user_id=current_user.id,
        project_id=project_id,
        member_id=member_id,
    )
    db.commit()
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# Versions
# ---------------------------------------------------------------------------


@router.get(
    "/reports/{report_id}/manuscripts/{manuscript_id}/versions",
    response_model=ManuscriptVersionListResponse,
)
def list_manuscript_versions(
    report_id: uuid.UUID,
    manuscript_id: uuid.UUID,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ManuscriptVersionListResponse:
    # Cross-user → 404 via project ownership check.
    _ = report_id
    rows, total = versions_svc.list_versions(
        db,
        actor_user_id=current_user.id,
        manuscript_id=manuscript_id,
        limit=limit,
        offset=offset,
    )
    return ManuscriptVersionListResponse(
        items=[
            ManuscriptVersionRead.model_validate(r) for r in rows
        ],
        total=total, limit=limit, offset=offset,
    )


@router.get(
    "/reports/{report_id}/manuscript-versions/{version_id}",
    response_model=ManuscriptVersionRead,
)
def get_manuscript_version(
    report_id: uuid.UUID,
    version_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ManuscriptVersionRead:
    _ = report_id
    version = versions_svc.get_version(
        db,
        actor_user_id=current_user.id,
        manuscript_version_id=version_id,
    )
    return ManuscriptVersionRead.model_validate(version)


# ---------------------------------------------------------------------------
# Branches
# ---------------------------------------------------------------------------


@router.post(
    "/reports/{report_id}/manuscript-branches",
    response_model=ManuscriptBranchRead,
)
def create_branch(
    report_id: uuid.UUID,
    body: BranchCreateRequest,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ManuscriptBranchRead:
    _ = report_id
    branch = branches_svc.create_branch(
        db,
        actor_user_id=current_user.id,
        manuscript_id=body.manuscript_id,
        name=body.name,
        head_version_id=body.head_version_id,
        is_default=body.is_default,
    )
    db.commit()
    db.refresh(branch)
    response.status_code = 201
    return ManuscriptBranchRead.model_validate(branch)


@router.get(
    "/reports/{report_id}/manuscripts/{manuscript_id}/branches",
    response_model=ManuscriptBranchListResponse,
)
def list_branches(
    report_id: uuid.UUID,
    manuscript_id: uuid.UUID,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ManuscriptBranchListResponse:
    _ = report_id
    rows, total = branches_svc.list_branches(
        db,
        actor_user_id=current_user.id,
        manuscript_id=manuscript_id,
        limit=limit,
        offset=offset,
    )
    return ManuscriptBranchListResponse(
        items=[
            ManuscriptBranchRead.model_validate(r) for r in rows
        ],
        total=total, limit=limit, offset=offset,
    )


@router.post(
    "/reports/{report_id}/manuscript-branches/merge",
    response_model=ManuscriptBranchRead,
)
def merge_branches(
    report_id: uuid.UUID,
    body: BranchMergeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ManuscriptBranchRead:
    _ = report_id
    target = merge_svc.merge_branches(
        db,
        actor_user_id=current_user.id,
        source_branch_id=body.source_branch_id,
        target_branch_id=body.target_branch_id,
        new_version_id=body.new_version_id,
        note=body.note,
    )
    db.commit()
    db.refresh(target)
    return ManuscriptBranchRead.model_validate(target)


# ---------------------------------------------------------------------------
# Comments
# ---------------------------------------------------------------------------


@router.post(
    "/reports/{report_id}/manuscript-versions/{version_id}/comments",
    response_model=ManuscriptCommentRead,
)
def create_comment(
    report_id: uuid.UUID,
    version_id: uuid.UUID,
    body: CommentCreateRequest,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ManuscriptCommentRead:
    _ = report_id
    comment = comments_svc.create_comment(
        db,
        actor_user_id=current_user.id,
        manuscript_version_id=version_id,
        body=body.body,
        manuscript_section_id=body.manuscript_section_id,
        parent_comment_id=body.parent_comment_id,
        anchor=body.anchor,
    )
    db.commit()
    db.refresh(comment)
    response.status_code = 201
    return ManuscriptCommentRead.model_validate(comment)


@router.get(
    "/reports/{report_id}/manuscript-versions/{version_id}/comments",
    response_model=ManuscriptCommentListResponse,
)
def list_comments(
    report_id: uuid.UUID,
    version_id: uuid.UUID,
    status: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ManuscriptCommentListResponse:
    _ = report_id
    rows, total = comments_svc.list_comments(
        db,
        actor_user_id=current_user.id,
        manuscript_version_id=version_id,
        status=status,
        limit=limit,
        offset=offset,
    )
    return ManuscriptCommentListResponse(
        items=[
            ManuscriptCommentRead.model_validate(r) for r in rows
        ],
        total=total, limit=limit, offset=offset,
    )


@router.post(
    "/reports/{report_id}/comments/{comment_id}/resolve",
    response_model=ManuscriptCommentRead,
)
def resolve_comment(
    report_id: uuid.UUID,
    comment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ManuscriptCommentRead:
    _ = report_id
    comment = comments_svc.resolve_comment(
        db,
        actor_user_id=current_user.id,
        comment_id=comment_id,
    )
    db.commit()
    db.refresh(comment)
    return ManuscriptCommentRead.model_validate(comment)


@router.post(
    "/reports/{report_id}/comments/{comment_id}/reopen",
    response_model=ManuscriptCommentRead,
)
def reopen_comment(
    report_id: uuid.UUID,
    comment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ManuscriptCommentRead:
    _ = report_id
    comment = comments_svc.reopen_comment(
        db,
        actor_user_id=current_user.id,
        comment_id=comment_id,
    )
    db.commit()
    db.refresh(comment)
    return ManuscriptCommentRead.model_validate(comment)


# ---------------------------------------------------------------------------
# Review tasks
# ---------------------------------------------------------------------------


@router.post(
    "/reports/{report_id}/manuscript-versions/{version_id}/reviews",
    response_model=ManuscriptReviewTaskRead,
)
def create_review_task(
    report_id: uuid.UUID,
    version_id: uuid.UUID,
    body: ReviewTaskCreateRequest,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ManuscriptReviewTaskRead:
    _ = report_id
    task = reviews_svc.create_review_task(
        db,
        actor_user_id=current_user.id,
        manuscript_version_id=version_id,
        title=body.title,
        description=body.description,
        severity=body.severity,
        assignee_user_id=body.assignee_user_id,
        scope=body.scope,
        related_section_id=body.related_section_id,
        related_qa_finding_id=body.related_qa_finding_id,
        related_citation_id=body.related_citation_id,
        due_at=body.due_at,
    )
    db.commit()
    db.refresh(task)
    response.status_code = 201
    return ManuscriptReviewTaskRead.model_validate(task)


@router.get(
    "/reports/{report_id}/manuscript-versions/{version_id}/reviews",
    response_model=ManuscriptReviewTaskListResponse,
)
def list_review_tasks(
    report_id: uuid.UUID,
    version_id: uuid.UUID,
    status: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ManuscriptReviewTaskListResponse:
    _ = report_id
    rows, total = reviews_svc.list_review_tasks(
        db,
        actor_user_id=current_user.id,
        manuscript_version_id=version_id,
        status=status,
        limit=limit,
        offset=offset,
    )
    return ManuscriptReviewTaskListResponse(
        items=[
            ManuscriptReviewTaskRead.model_validate(r) for r in rows
        ],
        total=total, limit=limit, offset=offset,
    )


@router.patch(
    "/reports/{report_id}/reviews/{review_task_id}",
    response_model=ManuscriptReviewTaskRead,
)
def change_review_status(
    report_id: uuid.UUID,
    review_task_id: uuid.UUID,
    body: ReviewTaskStatusChangeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ManuscriptReviewTaskRead:
    _ = report_id
    task = reviews_svc.change_review_status(
        db,
        actor_user_id=current_user.id,
        review_task_id=review_task_id,
        new_status=body.status,
        resolution=body.resolution,
    )
    db.commit()
    db.refresh(task)
    return ManuscriptReviewTaskRead.model_validate(task)


# Touch imported symbols to satisfy linters in dev; they are part of
# the public surface and future routes.
_ = get_project, perms, BranchCreateRequest


__all__ = ["router"]
