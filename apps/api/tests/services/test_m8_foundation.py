"""Smoke tests for M8 foundation wiring.

These tests validate the contracts the extraction service will rely
on in later phases: config defaults, exception codes, and the
``create_source_extracted_event`` guard behaviour.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

from app.core.config import get_settings
from app.core.exceptions import (
    DocumentFetchError,
    DocumentParseError,
    DocumentTooLargeError,
    NoExtractableTextError,
    ReportEventSourceMismatch,
    ReportEventValidationError,
    SourceDocumentUrlMissing,
    SourceNotFound,
    UnsafeUrlError,
    UnsupportedContentTypeError,
)
from app.db.session import SessionLocal
from app.services.report_events import create_source_extracted_event


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
def test_extraction_defaults_are_coherent() -> None:
    s = get_settings()
    assert s.document_fetch_timeout_seconds > 0
    assert s.document_max_bytes >= 1024
    assert s.document_max_redirects >= 0
    assert s.chunk_target_words > 0
    assert 0 <= s.chunk_overlap_words < s.chunk_target_words


def test_chunk_config_rejects_overlap_ge_target(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pydantic import ValidationError

    from app.core import config as cfg

    monkeypatch.setenv("CHUNK_TARGET_WORDS", "100")
    monkeypatch.setenv("CHUNK_OVERLAP_WORDS", "100")
    cfg.get_settings.cache_clear()
    try:
        with pytest.raises(ValidationError):
            cfg.Settings()
    finally:
        cfg.get_settings.cache_clear()

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------
def test_exception_codes_and_status() -> None:
    cases = [
        (SourceNotFound, "SOURCE_NOT_FOUND", 404),
        (DocumentFetchError, "DOCUMENT_FETCH_ERROR", 502),
        (UnsafeUrlError, "UNSAFE_URL", 422),
        (DocumentTooLargeError, "DOCUMENT_TOO_LARGE", 413),
        (UnsupportedContentTypeError, "UNSUPPORTED_CONTENT_TYPE", 422),
        (DocumentParseError, "DOCUMENT_PARSE_ERROR", 422),
        (NoExtractableTextError, "NO_EXTRACTABLE_TEXT", 422),
        (SourceDocumentUrlMissing, "SOURCE_DOCUMENT_URL_MISSING", 422),
        (ReportEventSourceMismatch, "REPORT_EVENT_SOURCE_MISMATCH", 500),
    ]
    for cls, code, status in cases:
        assert cls.code == code
        assert cls.status_code == status


# ---------------------------------------------------------------------------
# create_source_extracted_event guards
# ---------------------------------------------------------------------------
def _mk_user_and_source(
    *, content_hash: str | None, pipeline_version: str | None
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    with SessionLocal() as db:
        uid = db.execute(
            text(
                "INSERT INTO users (email, password_hash) "
                "VALUES (:e, 'h') RETURNING id"
            ),
            {"e": f"m8f-{uuid.uuid4().hex}@example.com"},
        ).scalar()
        rid = db.execute(
            text(
                "INSERT INTO reports "
                "(user_id, topic, status, output_language) "
                "VALUES (:u, 'T', 'draft', 'en') RETURNING id"
            ),
            {"u": uid},
        ).scalar()
        sid = db.execute(
            text(
                "INSERT INTO sources "
                "(report_id, title, status, content_hash, "
                " extraction_pipeline_version) "
                "VALUES (:r, 'T', 'full_text', :h, :p) RETURNING id"
            ),
            {"r": rid, "h": content_hash, "p": pipeline_version},
        ).scalar()
        db.commit()
    return uid, rid, sid


def test_create_source_extracted_event_requires_content_hash() -> None:
    uid, rid, sid = _mk_user_and_source(
        content_hash="a" * 64, pipeline_version="m8.1"
    )
    with SessionLocal() as db:
        with pytest.raises(ReportEventValidationError):
            create_source_extracted_event(
                db,
                report_id=rid,
                user_id=uid,
                source_id=sid,
                content_hash="",
                chunk_count=1,
                pipeline_version="m8.1",
            )
        db.rollback()


def test_create_source_extracted_event_rejects_mismatched_hash() -> None:
    uid, rid, sid = _mk_user_and_source(
        content_hash="a" * 64, pipeline_version="m8.1"
    )
    with SessionLocal() as db:
        with pytest.raises(ReportEventValidationError):
            create_source_extracted_event(
                db,
                report_id=rid,
                user_id=uid,
                source_id=sid,
                content_hash="b" * 64,
                chunk_count=1,
                pipeline_version="m8.1",
            )
        db.rollback()


def test_create_source_extracted_event_succeeds_on_match() -> None:
    uid, rid, sid = _mk_user_and_source(
        content_hash="a" * 64, pipeline_version="m8.1"
    )
    with SessionLocal() as db:
        event = create_source_extracted_event(
            db,
            report_id=rid,
            user_id=uid,
            source_id=sid,
            content_hash="a" * 64,
            chunk_count=3,
            pipeline_version="m8.1",
        )
        assert event.event_type == "source_extracted"
        assert event.event_meta["chunk_count"] == 3
        db.rollback()
