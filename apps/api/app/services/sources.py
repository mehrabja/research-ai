"""Source service.

Ownership filtering lives inside the SQL query, not only in the route.
This makes ownership part of the data-access boundary and prevents
cross-user access even if a future caller bypasses the HTTP route.

M7 adds discovery-side helpers on top of the original extraction-side
``get_source_for_report``. Nothing here touches extraction behaviour.
"""
from __future__ import annotations

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core import exceptions as app_exceptions
from app.core.config import get_settings
from app.core.exceptions import SourceNotFound
from app.db.models.project import Project
from app.db.models.source import Source
from app.domain.source import SourceCandidate
from app.integrations.sources.base import (
    SourceProviderAuthError,
    SourceProviderInvalidResponseError,
    SourceProviderRateLimitError,
    SourceProviderTimeoutError,
    SourceProviderUnavailableError,
    SourceSearchProvider,
)
from app.services.report_events import create_source_added_event
from app.services.reports import get_report
from app.services.usage_contract import ProviderUsage, record_provider_usage

logger = logging.getLogger(__name__)

_UNIQUE_VIOLATION = "23505"
_MAX_QUERY_LEN = 200


def get_source_for_report(
    db: Session,
    *,
    user_id: uuid.UUID,
    report_id: uuid.UUID,
    source_id: uuid.UUID,
) -> Source:
    """Return a source that belongs to the given report and user.

    Raises ``ReportNotFound`` if the report is missing, foreign, or
    soft-deleted. Raises ``SourceNotFound`` if the source is missing
    or does not belong to the report.
    """
    get_report(db, user_id=user_id, report_id=report_id)

    stmt = select(Source).where(
        Source.id == source_id,
        Source.report_id == report_id,
    )
    source = db.execute(stmt).scalar_one_or_none()
    if source is None:
        raise SourceNotFound()
    return source


def list_sources_for_report(
    db: Session,
    *,
    user_id: uuid.UUID,
    report_id: uuid.UUID,
) -> list[Source]:
    """Return all sources for an owned, active report.

    Deterministic ordering: ``created_at ASC, id ASC``.
    """
    get_report(db, user_id=user_id, report_id=report_id)
    stmt = (
        select(Source)
        .where(Source.report_id == report_id)
        .order_by(Source.created_at.asc(), Source.id.asc())
    )
    return list(db.execute(stmt).scalars().all())


def search_source_candidates(
    db: Session,
    *,
    user_id: uuid.UUID,
    report_id: uuid.UUID,
    query: str,
    limit: int | None,
    provider: SourceSearchProvider,
    year: int | None = None,
    open_access_only: bool = False,
    min_citations: int | None = None,
    max_citations: int | None = None,
    author: str | None = None,
    venue: str | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
    publication_type: str | None = None,
    language: str | None = None,
    sort_by: str = "relevance",
    sort_order: str = "desc",
) -> list[SourceCandidate]:
    """Discovery only. Never persists anything.

    Validates ownership and inputs, calls the provider, maps
    provider-level errors to typed AppErrors.
    """
    get_report(db, user_id=user_id, report_id=report_id)

    q = (query or "").strip()
    if not q:
        raise app_exceptions.SourceQueryInvalid(
            "query must be non-empty"
        )
    if len(q) > _MAX_QUERY_LEN:
        raise app_exceptions.SourceQueryInvalid(
            f"query must be <= {_MAX_QUERY_LEN} characters"
        )

    settings = get_settings()
    effective_limit = (
        settings.source_search_limit_default if limit is None else limit
    )
    if effective_limit < 1:
        raise app_exceptions.SourceQueryInvalid("limit must be >= 1")
    if effective_limit > settings.source_search_limit_max:
        effective_limit = settings.source_search_limit_max

    try:
        candidates = provider.search(
            query=q,
            limit=effective_limit,
            year=year,
            open_access_only=open_access_only,
        )
        author_q = author.strip().lower() if author else None
        venue_q = venue.strip().lower() if venue else None
        filtered: list[SourceCandidate] = []
        for candidate in candidates:
            if year is not None and candidate.year != year:
                continue
            if year_from is not None and (
                candidate.year is None or candidate.year < year_from
            ):
                continue
            if year_to is not None and (
                candidate.year is None or candidate.year > year_to
            ):
                continue
            if min_citations is not None and (
                candidate.citation_count is None
                or candidate.citation_count < min_citations
            ):
                continue
            if max_citations is not None and (
                candidate.citation_count is None
                or candidate.citation_count > max_citations
            ):
                continue
            if author_q and not any(
                author_q in person.lower()
                for person in (candidate.authors or ())
            ):
                continue
            if venue_q:
                meta = candidate.source_meta or {}
                venue_value = str(
                    meta.get("venue") or meta.get("journal") or ""
                ).lower()
                if venue_q not in venue_value:
                    continue
            if open_access_only:
                meta = candidate.source_meta or {}
                oa = meta.get("is_open_access")
                if oa is False:
                    continue
            if publication_type:
                meta = candidate.source_meta or {}
                type_value = str(meta.get("publication_type") or "").lower()
                if type_value and publication_type.lower() not in type_value:
                    continue
            if language:
                meta = candidate.source_meta or {}
                lang_value = str(meta.get("language") or "").lower()
                if lang_value and language.lower() != lang_value:
                    continue
            filtered.append(candidate)
        candidates = filtered

        if sort_by == "citations":
            def sort_key(candidate: SourceCandidate):
                return candidate.citation_count if candidate.citation_count is not None else -1
        elif sort_by == "year":
            def sort_key(candidate: SourceCandidate):
                return candidate.year if candidate.year is not None else -1
        elif sort_by == "title":
            def sort_key(candidate: SourceCandidate):
                return candidate.title.lower()
        else:
            def sort_key(candidate: SourceCandidate):
                return 0

        if sort_by != "relevance":
            candidates.sort(key=sort_key, reverse=sort_order == "desc")
        report = get_report(
            db,
            user_id=user_id,
            report_id=report_id,
        )
        project = db.get(Project, report.project_id)
        if project is not None:
            record_provider_usage(
                db,
                workspace_id=project.workspace_id,
                user_id=user_id,
                source_id=None,
                usage=ProviderUsage(
                    capability="source_discovery",
                    operation="source_search",
                    provider=getattr(provider, "provider_name", "unknown"),
                    model=None,
                    metric="search_requests",
                    units=1,
                    metadata={"query_length": len(q), "result_count": len(candidates), "min_citations": min_citations, "max_citations": max_citations, "author": author, "venue": venue, "year_from": year_from, "year_to": year_to, "publication_type": publication_type, "language": language, "sort_by": sort_by, "sort_order": sort_order, "open_access_only": open_access_only},
                ),
                idempotency_key=f"source-search:{uuid.uuid4()}",
            )
            db.commit()
        return candidates
    except SourceProviderTimeoutError as exc:
        raise app_exceptions.SourceProviderUnavailable() from exc
    except SourceProviderUnavailableError as exc:
        raise app_exceptions.SourceProviderUnavailable() from exc
    except SourceProviderRateLimitError as exc:
        raise app_exceptions.SourceProviderRateLimited() from exc
    except SourceProviderAuthError as exc:
        raise app_exceptions.SourceProviderAuthError() from exc
    except SourceProviderInvalidResponseError as exc:
        raise app_exceptions.SourceProviderInvalidResponse() from exc

def create_source_from_candidate(
    db: Session,
    *,
    user_id: uuid.UUID,
    report_id: uuid.UUID,
    candidate: SourceCandidate,
) -> tuple[Source, bool]:
    """Idempotent Source registration.

    Returns ``(source, was_created)``. If a Source with the same
    ``(report_id, source_api, external_source_id)`` already exists,
    it is returned with ``was_created=False`` and no new event is
    written. Otherwise the Source is created, a ``source_added``
    audit event is emitted in the same transaction, and
    ``was_created=True`` is returned.
    """
    get_report(db, user_id=user_id, report_id=report_id)

    existing = db.execute(
        select(Source).where(
            Source.report_id == report_id,
            Source.source_api == candidate.source_api,
            Source.external_source_id == candidate.external_source_id,
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing, False

    try:
        source = Source(
            report_id=report_id,
            title=candidate.title,
            authors=(
                list(candidate.authors) if candidate.authors else None
            ),
            year=candidate.year,
            doi=candidate.doi,
            url=candidate.url,
            source_api=candidate.source_api,
            external_source_id=candidate.external_source_id,
            citation_count=candidate.citation_count,
            abstract=candidate.abstract,
            source_meta=candidate.source_meta,
            status="metadata_only",
        )
        db.add(source)
        db.flush()

        create_source_added_event(
            db,
            report_id=report_id,
            user_id=user_id,
            source_id=source.id,
            source_api=candidate.source_api,
            external_source_id=candidate.external_source_id,
            title=candidate.title,
        )
        db.commit()
        db.refresh(source)
        return source, True
    except IntegrityError as exc:
        db.rollback()
        sqlstate = getattr(exc.orig, "sqlstate", None)
        if sqlstate != _UNIQUE_VIOLATION:
            raise
        existing = db.execute(
            select(Source).where(
                Source.report_id == report_id,
                Source.source_api == candidate.source_api,
                Source.external_source_id
                == candidate.external_source_id,
            )
        ).scalar_one_or_none()
        if existing is None:
            raise
        return existing, False
    except Exception:
        db.rollback()
        raise

__all__ = [
    "create_source_from_candidate",
    "get_source_for_report",
    "list_sources_for_report",
    "search_source_candidates",
]
