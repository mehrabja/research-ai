"""Idempotency key semantics for generation enqueue."""
from __future__ import annotations

import uuid

from sqlalchemy import text

from app.db.session import SessionLocal
from app.services import generation_jobs


def _seed() -> tuple[uuid.UUID, uuid.UUID]:
    with SessionLocal() as db:
        uid = db.execute(text(
            "INSERT INTO users (email, password_hash) "
            "VALUES (:e, 'h') RETURNING id"
        ), {"e": f"rg-{uuid.uuid4().hex}@example.com"}).scalar()
        rid = db.execute(text(
            "INSERT INTO reports "
            "(user_id, topic, status, output_language) "
            "VALUES (:u, 'T', 'draft', 'en') RETURNING id"
        ), {"u": uid}).scalar()
        db.commit()
    return uid, rid


def test_same_caller_key_returns_same_job() -> None:
    uid, rid = _seed()
    with SessionLocal() as db:
        r1 = generation_jobs.enqueue_report_generation_job(
            db, user_id=uid, report_id=rid,
            idempotency_key="user-key-abc",
        )
    with SessionLocal() as db:
        r2 = generation_jobs.enqueue_report_generation_job(
            db, user_id=uid, report_id=rid,
            idempotency_key="user-key-abc",
        )
    assert r1.job.id == r2.job.id


def test_different_caller_key_creates_new_job() -> None:
    uid, rid = _seed()
    with SessionLocal() as db:
        r1 = generation_jobs.enqueue_report_generation_job(
            db, user_id=uid, report_id=rid, idempotency_key="key-1",
        )
    with SessionLocal() as db:
        r2 = generation_jobs.enqueue_report_generation_job(
            db, user_id=uid, report_id=rid, idempotency_key="key-2",
        )
    assert r1.job.id != r2.job.id
