"""M34 — Collaboration Pydantic schemas."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Members
# ---------------------------------------------------------------------------


class MemberAddRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: uuid.UUID
    role: str


class MemberChangeRoleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: str


class ProjectMemberRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: uuid.UUID
    project_id: uuid.UUID
    user_id: uuid.UUID
    role: str
    added_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class ProjectMemberListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[ProjectMemberRead]
    total: int
    limit: int
    offset: int


# ---------------------------------------------------------------------------
# Versions
# ---------------------------------------------------------------------------


class ManuscriptVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: uuid.UUID
    manuscript_id: uuid.UUID
    version: int
    status: str
    architecture_version: str
    template_version: str
    parent_version_id: uuid.UUID | None
    context_hash: str
    title: str
    word_target: int
    created_at: datetime


class ManuscriptVersionListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[ManuscriptVersionRead]
    total: int
    limit: int
    offset: int


# ---------------------------------------------------------------------------
# Branches
# ---------------------------------------------------------------------------


class BranchCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    manuscript_id: uuid.UUID
    name: str = Field(min_length=1, max_length=200)
    head_version_id: uuid.UUID
    is_default: bool = False


class BranchMergeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_branch_id: uuid.UUID
    target_branch_id: uuid.UUID
    new_version_id: uuid.UUID
    note: str | None = None


class ManuscriptBranchRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: uuid.UUID
    manuscript_id: uuid.UUID
    name: str
    head_version_id: uuid.UUID
    is_default: bool
    created_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class ManuscriptBranchListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[ManuscriptBranchRead]
    total: int
    limit: int
    offset: int


# ---------------------------------------------------------------------------
# Comments
# ---------------------------------------------------------------------------


class CommentCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    body: str = Field(min_length=1, max_length=20000)
    manuscript_section_id: uuid.UUID | None = None
    parent_comment_id: uuid.UUID | None = None
    anchor: dict[str, Any] | None = None


class ManuscriptCommentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: uuid.UUID
    project_id: uuid.UUID
    report_id: uuid.UUID
    manuscript_version_id: uuid.UUID
    manuscript_section_id: uuid.UUID | None
    parent_comment_id: uuid.UUID | None
    author_user_id: uuid.UUID
    body: str
    status: str
    anchor: dict[str, Any] | None
    resolved_by: uuid.UUID | None
    resolved_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ManuscriptCommentListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[ManuscriptCommentRead]
    total: int
    limit: int
    offset: int


# ---------------------------------------------------------------------------
# Review tasks
# ---------------------------------------------------------------------------


class ReviewTaskCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    manuscript_version_id: uuid.UUID
    title: str = Field(min_length=1, max_length=500)
    description: str | None = None
    severity: str = "info"
    assignee_user_id: uuid.UUID | None = None
    scope: dict[str, Any] | None = None
    related_section_id: uuid.UUID | None = None
    related_qa_finding_id: uuid.UUID | None = None
    related_citation_id: uuid.UUID | None = None
    due_at: datetime | None = None


class ReviewTaskStatusChangeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: str
    resolution: dict[str, Any] | None = None


class ManuscriptReviewTaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: uuid.UUID
    project_id: uuid.UUID
    report_id: uuid.UUID
    manuscript_version_id: uuid.UUID
    assignee_user_id: uuid.UUID | None
    created_by_user_id: uuid.UUID
    title: str
    description: str | None
    scope: dict[str, Any] | None
    severity: str
    status: str
    related_section_id: uuid.UUID | None
    related_qa_finding_id: uuid.UUID | None
    related_citation_id: uuid.UUID | None
    due_at: datetime | None
    resolution: dict[str, Any] | None
    resolved_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ManuscriptReviewTaskListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[ManuscriptReviewTaskRead]
    total: int
    limit: int
    offset: int
