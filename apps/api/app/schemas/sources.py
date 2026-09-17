"""Pydantic schemas for source discovery (M7)."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SourceCandidateRead(BaseModel):
    source_api: str
    external_source_id: str
    title: str
    authors: list[str] | None = None
    year: int | None = None
    doi: str | None = None
    url: str | None = None
    abstract: str | None = None
    citation_count: int | None = None


class SourceSearchResponse(BaseModel):
    query: str
    limit: int
    candidates: list[SourceCandidateRead]


class SourceCreateRequest(BaseModel):
    source_api: str
    external_source_id: str
    title: str
    authors: list[str] | None = None
    year: int | None = None
    doi: str | None = None
    url: str | None = None
    abstract: str | None = None
    citation_count: int | None = None


class SourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    report_id: uuid.UUID
    title: str
    authors: list[str] | None
    year: int | None
    doi: str | None
    url: str | None
    source_api: str | None
    external_source_id: str | None
    citation_count: int | None
    abstract: str | None
    status: str
    created_at: datetime
    updated_at: datetime


class SourceListResponse(BaseModel):
    items: list[SourceRead]
