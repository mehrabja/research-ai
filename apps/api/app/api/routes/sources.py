"""Source routes.

- POST   /reports/{report_id}/sources/{source_id}/extract   (M8)
- GET    /reports/{report_id}/sources/search                 (M7)
- GET    /reports/{report_id}/sources                        (M7)
- POST   /reports/{report_id}/sources                        (M7)
- GET    /reports/{report_id}/sources/{source_id}            (M7)

Route ordering matters: ``/search`` must be declared BEFORE
``/{source_id}`` so FastAPI does not attempt to parse ``search``
as a UUID.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.config import get_settings
from app.db.models.user import User
from app.db.session import get_db
from app.domain.source import SourceCandidate
from app.integrations.sources import (
    ArxivProvider,
    CrossrefProvider,
    EuropePMCProvider,
    OpenAlexProvider,
    PubMedProvider,
    SemanticScholarProvider,
)
from app.integrations.sources.base import SourceSearchProvider
from app.schemas.source_extraction import SourceExtractionResponse
from app.schemas.sources import (
    SourceCandidateRead,
    SourceCreateRequest,
    SourceListResponse,
    SourceRead,
    SourceSearchResponse,
)
from app.services import extraction as extraction_service
from app.services import sources as sources_service

router = APIRouter(
    prefix="/reports",
    tags=["sources"],
)


# ---------------------------------------------------------------------------
# Provider dependency (overridable in tests)
# ---------------------------------------------------------------------------
def _default_provider() -> SourceSearchProvider:
    settings = get_settings()
    if settings.source_search_provider == "openalex":
        return OpenAlexProvider(
            api_key=settings.openalex_api_key,
            timeout_seconds=settings.openalex_timeout_seconds,
            max_retries=settings.openalex_max_retries,
            min_interval_seconds=settings.openalex_min_interval_seconds,
        )
    if settings.source_search_provider == "arxiv":
        return ArxivProvider(
            timeout_seconds=settings.arxiv_timeout_seconds,
            max_retries=settings.arxiv_max_retries,
            min_interval_seconds=settings.arxiv_min_interval_seconds,
        )
    if settings.source_search_provider == "crossref":
        return CrossrefProvider(
            mailto=settings.crossref_mailto,
            api_key=settings.crossref_api_key,
            timeout_seconds=settings.crossref_timeout_seconds,
            max_retries=settings.crossref_max_retries,
            min_interval_seconds=settings.crossref_min_interval_seconds,
        )
    if settings.source_search_provider == "europepmc":
        return EuropePMCProvider(
            base_url=settings.europepmc_base_url,
            timeout_seconds=settings.europepmc_timeout_seconds,
            max_retries=settings.europepmc_max_retries,
            min_interval_seconds=settings.europepmc_min_interval_seconds,
        )
    if settings.source_search_provider == "pubmed":
        return PubMedProvider(
            api_key=settings.pubmed_api_key,
            email=settings.pubmed_email,
            tool=settings.pubmed_tool,
            base_url=settings.pubmed_base_url,
            timeout_seconds=settings.pubmed_timeout_seconds,
            max_retries=settings.pubmed_max_retries,
            min_interval_seconds=settings.pubmed_min_interval_seconds,
        )
    return SemanticScholarProvider(
        api_key=settings.semantic_scholar_api_key,
        base_url=settings.semantic_scholar_base_url,
        timeout_seconds=settings.semantic_scholar_timeout_seconds,
        max_retries=settings.semantic_scholar_max_retries,
    )


# ---------------------------------------------------------------------------
# M8 — extraction (unchanged)
# ---------------------------------------------------------------------------
@router.post(
    "/{report_id}/sources/{source_id}/extract",
    response_model=SourceExtractionResponse,
    summary="Fetch, extract, normalize, and chunk a source document",
)
def extract_source(
    report_id: uuid.UUID,
    source_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SourceExtractionResponse:
    result = extraction_service.extract_source(
        db,
        user_id=current_user.id,
        report_id=report_id,
        source_id=source_id,
    )
    return SourceExtractionResponse(
        source_id=result.source_id,
        status=result.status,
        content_hash=result.content_hash,
        chunk_count=result.chunk_count,
        content_type=result.content_type,
        content_length=result.content_length,
        extracted_at=result.extracted_at,
        pipeline_version=result.pipeline_version,
    )


# ---------------------------------------------------------------------------
# M7 — discovery
# ---------------------------------------------------------------------------
@router.get(
    "/{report_id}/sources/search",
    response_model=SourceSearchResponse,
    summary="Search external providers for source candidates",
)
def search_sources(
    report_id: uuid.UUID,
    q: str = Query(..., min_length=1, max_length=200),
    limit: int | None = Query(default=None, ge=1),
    year: int | None = Query(default=None, ge=1000, le=2200),
    open_access: bool = Query(default=False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    provider: SourceSearchProvider = Depends(_default_provider),
) -> SourceSearchResponse:
    candidates = sources_service.search_source_candidates(
        db,
        user_id=current_user.id,
        report_id=report_id,
        query=q,
        limit=limit,
        provider=provider,
        year=year,
        open_access_only=open_access,
    )
    settings = get_settings()
    effective_limit = (
        settings.source_search_limit_default if limit is None else limit
    )
    if effective_limit > settings.source_search_limit_max:
        effective_limit = settings.source_search_limit_max
    return SourceSearchResponse(
        query=q.strip(),
        limit=effective_limit,
        candidates=[
            SourceCandidateRead(
                source_api=c.source_api,
                external_source_id=c.external_source_id,
                title=c.title,
                authors=list(c.authors) if c.authors else None,
                year=c.year,
                doi=c.doi,
                url=c.url,
                abstract=c.abstract,
                citation_count=c.citation_count,
            )
            for c in candidates
        ],
    )


@router.get(
    "/{report_id}/sources",
    response_model=SourceListResponse,
    summary="List sources registered for a report",
)
def list_sources(
    report_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SourceListResponse:
    rows = sources_service.list_sources_for_report(
        db,
        user_id=current_user.id,
        report_id=report_id,
    )
    return SourceListResponse(
        items=[SourceRead.model_validate(r) for r in rows]
    )


@router.post(
    "/{report_id}/sources",
    response_model=SourceRead,
    status_code=201,
    summary="Register a source from a candidate (idempotent)",
)
def create_source(
    report_id: uuid.UUID,
    payload: SourceCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SourceRead:
    candidate = SourceCandidate(
        source_api=payload.source_api,
        external_source_id=payload.external_source_id,
        title=payload.title,
        authors=(
            tuple(payload.authors) if payload.authors else None
        ),
        year=payload.year,
        doi=payload.doi,
        url=payload.url,
        abstract=payload.abstract,
        citation_count=payload.citation_count,
    )
    source, _was_created = sources_service.create_source_from_candidate(
        db,
        user_id=current_user.id,
        report_id=report_id,
        candidate=candidate,
    )
    return SourceRead.model_validate(source)


@router.get(
    "/{report_id}/sources/{source_id}",
    response_model=SourceRead,
    summary="Get a single source by id",
)
def get_source(
    report_id: uuid.UUID,
    source_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SourceRead:
    source = sources_service.get_source_for_report(
        db,
        user_id=current_user.id,
        report_id=report_id,
        source_id=source_id,
    )
    return SourceRead.model_validate(source)
