from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field


class InvitationCreate(BaseModel):
    email: EmailStr
    role: Literal["admin", "member", "viewer"]
    ttl_days: int | None = Field(default=None, ge=1, le=365)


class InvitationRead(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    email: str
    role: str
    state: str
    expires_at: datetime
    accepted_at: datetime | None
    revoked_at: datetime | None
    created_at: datetime


class InvitationCreated(BaseModel):
    invitation: InvitationRead
    token: str  # raw token, returned exactly once


class InvitationListResponse(BaseModel):
    items: list[InvitationRead]
    total: int


class MemberRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    email: str | None = None
    full_name: str | None = None
    role: str
    status: str
    created_at: datetime


class MemberRoleUpdate(BaseModel):
    role: Literal["admin", "member", "viewer"]


class MemberListResponse(BaseModel):
    items: list[MemberRead]
    total: int


class InvitationAcceptRequest(BaseModel):
    token: str = Field(..., min_length=32, max_length=512)


class InvitationAcceptResponse(BaseModel):
    workspace_id: uuid.UUID
    user_id: uuid.UUID
    role: str
    status: str
