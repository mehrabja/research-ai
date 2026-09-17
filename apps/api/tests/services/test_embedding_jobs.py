"""Tests for the M11 embedding enqueue helper."""
from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from sqlalchemy import text

from app.core.exceptions import AppError
from app.db.session import SessionLocal
from app.services import embedding_jobs
from app.services.embedding_jobs import (
    build_embedding_job_idempotency_key,
)


def _mk_user() -> uuid.UUID:
    with SessionLocal() as db:
        uid = db.execute(
            text(
                "INSERT INTO users (email, password_hash) "
                "VALUES (:e, 'h') RETURNING id"
            ),
            {"e": f"mj-{uuid.uuid4().hex}@example.com"},
        ).scalar()
        db.commit()
    return uid


def _mk_report(*, uid: uuid.UUID) -> uuid.UUID:
    with SessionLocal() as db:
        rid = db.execute(
            text(
                "INSERT INTO reports "
                "(user_id, topic, status, output_language) "
                "VALUES (:u, 'T', 'draft', 'en') RETURNING id"
            ),
            {"u": uid},
        ).scalar()
        db.commit()
    return rid


def _mk_source(*, report_id: uuid.UUID) -> uuid.UUID:
    with SessionLocal() as db:
        sid = db.execute(
            text(
                "INSERT INTO sources (report_id, title, status) "
                "VALUES (:r, 'T', 'full_text') RETURNING id"
            ),
            {"r": report_id},
        ).scalar()
        db.commit()
    return sid


def test_build_key_is_deterministic() -> None:
    rid = uuid.uuid4()
    sid = uuid.uuid4()
    k1 = build_embedding_job_idempotency_key(
        report_id=rid, source_id=sid, profile_id="p1"
    )
    k2 = build_embedding_job_idempotency_key(
        report_id=rid, source_id=sid, profile_id="p1"
    )
    assert k1 == k2


def test_build_key_differs_by_profile() -> None:
    rid = uuid.uuid4()
    sid = uuid.uuid4()
    k1 = build_embedding_job_idempotency_key(
        report_id=rid, source_id=sid, profile_id="p1"
    )
    k2 = build_embedding_job_idempotency_key(
        report_id=rid, source_id=sid, profile_id="p2"
    )
    assert k1 != k2


def test_build_key_differs_by_source() -> None:
    rid = uuid.uuid4()
    k1 = build_embedding_job_idempotency_key(
        report_id=rid, source_id=uuid.uuid4(), profile_id="p1"
    )
    k2 = build_embedding_job_idempotency_key(
        report_id=rid, source_id=uuid.uuid4(), profile_id="p1"
    )
    assert k1 != k2


def test_enqueue_creates_job() -> None:
    uid = _mk_user()
    rid = _mk_report(uid=uid)
    sid = _mk_source(report_id=rid)
    with SessionLocal() as db:
        result = embedding_jobs.enqueue_source_embedding_job(
            db, user_id=uid, report_id=rid, source_id=sid,
        )
    assert result.created is True
    assert result.job.job_type == "embedding_source"
    assert result.job.status == "queued"
    assert result.job.payload["report_id"] == str(rid)
    assert result.job.payload["source_id"] == str(sid)


def test_duplicate_enqueue_returns_same_job() -> None:
    uid = _mk_user()
    rid = _mk_report(uid=uid)
    sid = _mk_source(report_id=rid)
    with SessionLocal() as db:
        r1 = embedding_jobs.enqueue_source_embedding_job(
            db, user_id=uid, report_id=rid, source_id=sid,
        )
    with SessionLocal() as db:
        r2 = embedding_jobs.enqueue_source_embedding_job(
            db, user_id=uid, report_id=rid, source_id=sid,
        )
    assert r1.job.id == r2.job.id
    assert r2.created is False


def test_source_report_mismatch_rejected() -> None:
    uid = _mk_user()
    rid_a = _mk_report(uid=uid)
    rid_b = _mk_report(uid=uid)
    sid_a = _mk_source(report_id=rid_a)

    with SessionLocal() as db, pytest.raises(AppError):
        embedding_jobs.enqueue_source_embedding_job(
            db,
            user_id=uid,
            report_id=rid_b,
            source_id=sid_a,
        )


def test_foreign_report_rejected() -> None:
    uid_a = _mk_user()
    uid_b = _mk_user()
    rid_b = _mk_report(uid=uid_b)
    sid_b = _mk_source(report_id=rid_b)

    with SessionLocal() as db, pytest.raises(AppError):
        embedding_jobs.enqueue_source_embedding_job(
            db,
            user_id=uid_a,
            report_id=rid_b,
            source_id=sid_b,
        )


def test_enqueue_does_not_call_provider() -> None:
    uid = _mk_user()
    rid = _mk_report(uid=uid)
    sid = _mk_source(report_id=rid)

    with patch(
        "app.integrations.embeddings.openai.OpenAIEmbeddingProvider"
        ".embed_documents",
    ) as mock_embed:
        with SessionLocal() as db:
            embedding_jobs.enqueue_source_embedding_job(
                db, user_id=uid, report_id=rid, source_id=sid,
            )
        mock_embed.assert_not_called()
