"""Retryable error leaves report 'generating'; retry succeeds."""
from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text

from app.db.models.jobs import Job
from app.db.session import SessionLocal
from app.integrations.generation.base import (
    GenerationRateLimitError,
)
from app.services import generation_jobs
from app.workers.runner import Worker


@pytest.fixture(autouse=True)
def _register_handlers() -> None:
    from app.workers.handlers import register_all_handlers
    register_all_handlers()


@pytest.fixture(autouse=True)
def _isolate_jobs() -> Iterator[None]:
    with SessionLocal() as db:
        db.execute(text("DELETE FROM jobs"))
        db.commit()
    yield
    with SessionLocal() as db:
        db.execute(text("DELETE FROM jobs"))
        db.commit()


def _seed() -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    with SessionLocal() as db:
        uid = db.execute(text(
            "INSERT INTO users (email, password_hash) "
            "VALUES (:e, 'h') RETURNING id"
        ), {"e": f"rt-{uuid.uuid4().hex}@example.com"}).scalar()
        rid = db.execute(text(
            "INSERT INTO reports "
            "(user_id, topic, status, output_language) "
            "VALUES (:u, 'T', 'draft', 'en') RETURNING id"
        ), {"u": uid}).scalar()
        db.commit()
    with SessionLocal() as db:
        r = generation_jobs.enqueue_report_generation_job(
            db, user_id=uid, report_id=rid,
        )
        jid = r.job.id
    return uid, rid, jid


def _rc(rid):  # type: ignore[no-untyped-def]
    from app.domain.retrieval import RetrievedChunk
    return RetrievedChunk(
        chunk_id=uuid.uuid4(), source_id=uuid.uuid4(), report_id=rid,
        chunk_index=0, content="ev", char_start=0, char_end=2,
        page_number=None, vector_distance=0.1, vector_similarity=0.9,
        lexical_score=0.5, vector_rank=1, lexical_rank=1,
        fusion_score=0.05, final_rank=1,
    )


def test_rate_limit_keeps_report_generating(
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    uid, rid, jid = _seed()
    monkeypatch.setattr(
        "app.services.generation.retrieval_service.retrieve",
        lambda *a, **k: ([_rc(rid)], {}),
    )
    from app.integrations.generation.openai import (
        OpenAIGenerationProvider,
    )
    def _rl(self, **_):  # type: ignore[no-untyped-def]
        raise GenerationRateLimitError("429")
    monkeypatch.setattr(OpenAIGenerationProvider, "generate", _rl)

    Worker(worker_id="w-rt")._claim_once()

    with SessionLocal() as db:
        job = db.get(Job, jid)
        run_status = db.execute(text(
            "SELECT status FROM generation_runs "
            "WHERE report_id = :r ORDER BY created_at DESC LIMIT 1"
        ), {"r": rid}).scalar()
        report_status = db.execute(text(
            "SELECT status FROM reports WHERE id = :r"
        ), {"r": rid}).scalar()
    assert job is not None and job.status == "retrying"
    assert run_status == "running"
    assert report_status == "generating"


def test_success_on_retry_completes(
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    uid, rid, jid = _seed()
    monkeypatch.setattr(
        "app.services.generation.retrieval_service.retrieve",
        lambda *a, **k: ([_rc(rid)], {}),
    )
    from app.domain.generation import GenerationProviderResult
    from app.integrations.generation.openai import (
        OpenAIGenerationProvider,
    )
    calls = {"n": 0}
    def _flaky(self, **_):  # type: ignore[no-untyped-def]
        calls["n"] += 1
        if calls["n"] == 1:
            raise GenerationRateLimitError("429")
        return GenerationProviderResult(
            text="draft.", provider="openai", model="m",
        )
    monkeypatch.setattr(OpenAIGenerationProvider, "generate", _flaky)

    Worker(worker_id="w-rt-1")._claim_once()

    # Rewind available_at to a time the worker's Python clock is
    # certain to be past. Postgres runs in a container whose clock may
    # be ahead of the host by a few milliseconds.
    past = datetime.now(UTC) - timedelta(hours=1)
    with SessionLocal() as db:
        db.execute(text(
            "UPDATE jobs SET status='queued', available_at=:t "
            "WHERE id = :j"
        ), {"j": jid, "t": past})
        db.commit()

    Worker(worker_id="w-rt-2")._claim_once()

    with SessionLocal() as db:
        job = db.get(Job, jid)
        report_status = db.execute(text(
            "SELECT status FROM reports WHERE id = :r"
        ), {"r": rid}).scalar()
        versions = db.execute(text(
            "SELECT COUNT(*) FROM report_versions WHERE report_id = :r"
        ), {"r": rid}).scalar()
    assert job is not None and job.status == "completed"
    assert report_status == "review_1"
    assert versions == 1
