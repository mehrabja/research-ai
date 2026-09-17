"""Source extraction service.

Owns the full lifecycle:
  authorize -> fetch -> extract (raw pages) -> canonicalize
  -> validate invariants -> hash -> chunk -> validate chunks
  -> persist -> audit event -> commit.

Failure boundaries
------------------
Pre-persistence failures call ``_record_failure`` (which commits only
``extraction_error``).

Persistence failures call ``db.rollback(); raise`` — never
``_record_failure``. The last known-good state is preserved exactly.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import (
    DocumentFetchError,
    DocumentParseError,
    DocumentTooLargeError,
    NoExtractableTextError,
    SourceDocumentUrlMissing,
    UnsafeUrlError,
    UnsupportedContentTypeError,
)
from app.db.models.source import Chunk, Source
from app.domain.extraction import (
    EXTRACTION_PIPELINE_VERSION,
    CanonicalInvariantError,
    ChunkInvariantError,
    build_canonical_document,
    to_page_boundaries,
    validate_canonical_document,
    validate_chunks,
    validate_hash_invariant,
)
from app.domain.text_chunking import WordTextChunker
from app.domain.text_hashing import compute_content_hash
from app.integrations.documents.extractors import (
    ExtractorError,
    ParseFetcherError,
    get_extractor,
)
from app.integrations.documents.fetcher import (
    DocumentFetchFetcherError,
    DocumentTooLargeFetcherError,
    FetcherError,
    UnsafeUrlFetcherError,
    fetch_document,
)
from app.services.report_events import create_source_extracted_event
from app.services.reports import get_report
from app.services.sources import get_source_for_report

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ExtractionResult:
    source_id: uuid.UUID
    status: str
    content_hash: str | None
    chunk_count: int
    content_type: str | None
    content_length: int | None
    extracted_at: datetime | None
    pipeline_version: str


def extract_source(
    db: Session,
    *,
    user_id: uuid.UUID,
    report_id: uuid.UUID,
    source_id: uuid.UUID,
) -> ExtractionResult:
    # 1. Authorize.
    get_report(db, user_id=user_id, report_id=report_id)
    source = get_source_for_report(
        db, user_id=user_id, report_id=report_id, source_id=source_id
    )

    # 2. URL presence.
    if not source.url:
        _record_failure(db, source, "no_url")
        raise SourceDocumentUrlMissing()

    settings = get_settings()

    # 3. Fetch.
    try:
        fetched = fetch_document(
            source.url,
            max_bytes=settings.document_max_bytes,
            timeout_seconds=settings.document_fetch_timeout_seconds,
            max_redirects=settings.document_max_redirects,
        )
    except UnsafeUrlFetcherError as exc:
        _record_failure(db, source, "unsafe_url")
        raise UnsafeUrlError() from exc
    except DocumentTooLargeFetcherError as exc:
        _record_failure(db, source, "too_large")
        raise DocumentTooLargeError() from exc
    except DocumentFetchFetcherError as exc:
        _record_failure(db, source, "fetch_error")
        raise DocumentFetchError() from exc
    except FetcherError as exc:
        _record_failure(db, source, "fetch_error")
        raise DocumentFetchError() from exc

    # 4. Extract raw pages.
    extractor = get_extractor(fetched.content_type)
    if extractor is None:
        _record_failure(db, source, "unsupported_content_type")
        raise UnsupportedContentTypeError()

    try:
        extracted = extractor.extract(
            content=fetched.content, content_type=fetched.content_type
        )
    except ParseFetcherError as exc:
        _record_failure(db, source, "parse_error")
        raise DocumentParseError() from exc
    except ExtractorError as exc:
        _record_failure(db, source, "parse_error")
        raise DocumentParseError() from exc

    # 5. Canonicalize.
    canonical = build_canonical_document(extracted)
    if not canonical.text.strip():
        _record_failure(db, source, "no_text")
        raise NoExtractableTextError()

    try:
        validate_canonical_document(canonical)
    except CanonicalInvariantError as exc:
        _record_failure(db, source, "canonical_invariant")
        raise DocumentParseError() from exc

    new_hash = compute_content_hash(canonical.text)

    # 6. Idempotency: content hash + full_text + pipeline version
    #    + contiguous chunks.
    unchanged = (
        source.content_hash == new_hash
        and source.full_text == canonical.text
        and source.extraction_pipeline_version
        == EXTRACTION_PIPELINE_VERSION
    )

    chunk_summary = db.execute(
        select(
            func.count(Chunk.id),
            func.max(Chunk.chunk_index),
        ).where(Chunk.source_id == source.id)
    ).one()

    existing_count, max_chunk_index = chunk_summary

    chunks_current = (
        existing_count > 0
        and max_chunk_index is not None
        and max_chunk_index == existing_count - 1
    )

    if unchanged and chunks_current:
        return ExtractionResult(
            source_id=source.id,
            status=source.status,
            content_hash=source.content_hash,
            chunk_count=existing_count,
            content_type=source.content_type,
            content_length=source.content_length,
            extracted_at=source.extracted_at,
            pipeline_version=(
                source.extraction_pipeline_version or ""
            ),
        )

    # 7. Chunk + validate.
    boundaries = to_page_boundaries(canonical)
    chunker = WordTextChunker(
        target_words=settings.chunk_target_words,
        overlap_words=settings.chunk_overlap_words,
        page_boundaries=boundaries,
    )
    chunks = chunker.chunk(canonical.text)
    if not chunks:
        _record_failure(db, source, "no_chunks")
        raise NoExtractableTextError()

    try:
        validate_chunks(chunks, canonical.text)
    except ChunkInvariantError as exc:
        _record_failure(db, source, "chunk_invariant")
        raise DocumentParseError() from exc

    try:
        validate_hash_invariant(canonical.text, new_hash)
    except CanonicalInvariantError as exc:
        _record_failure(db, source, "hash_invariant")
        raise DocumentParseError() from exc

    # 8. Persistence — the ONLY block where rollback+raise is used.
    try:
        source.full_text = canonical.text
        source.content_hash = new_hash
        source.content_type = fetched.content_type
        source.content_length = fetched.content_length
        source.extracted_at = datetime.now(UTC)
        source.extraction_error = None
        source.extraction_pipeline_version = (
            EXTRACTION_PIPELINE_VERSION
        )
        source.status = "full_text"

        db.execute(delete(Chunk).where(Chunk.source_id == source.id))
        for c in chunks:
            db.add(
                Chunk(
                    source_id=source.id,
                    content=c.content,
                    chunk_index=c.chunk_index,
                    char_start=c.char_start,
                    char_end=c.char_end,
                    page_number=c.page_number,
                )
            )

        create_source_extracted_event(
            db,
            report_id=report_id,
            user_id=user_id,
            source_id=source.id,
            content_hash=new_hash,
            chunk_count=len(chunks),
            pipeline_version=EXTRACTION_PIPELINE_VERSION,
        )

        db.commit()
        db.refresh(source)
    except Exception:
        # Persistence failures MUST NOT call _record_failure. The
        # previous successful state stays exactly intact.
        db.rollback()
        raise

    return ExtractionResult(
        source_id=source.id,
        status=source.status,
        content_hash=source.content_hash,
        chunk_count=len(chunks),
        content_type=source.content_type,
        content_length=source.content_length,
        extracted_at=source.extracted_at,
        pipeline_version=EXTRACTION_PIPELINE_VERSION,
    )


# ---------------------------------------------------------------------------
# Failure recording (ONLY for pre-persistence failures)
# ---------------------------------------------------------------------------
def _record_failure(db: Session, source: Source, code: str) -> None:
    """Commit a controlled failure state without destroying prior success.

    Touches only ``extraction_error`` and, when no prior content
    exists, ``status``. Never modifies ``full_text``, ``content_hash``,
    ``content_type``, ``content_length``, ``extracted_at``, or
    ``extraction_pipeline_version``.
    """
    try:
        source.extraction_error = code
        if not source.full_text:
            source.status = "extraction_failed"
        db.commit()
        db.refresh(source)
    except Exception:
        db.rollback()
        raise


__all__ = ["ExtractionResult", "extract_source"]
