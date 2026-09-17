"""Worker marks run + report failed on permanent provider error."""
from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import text

from app.db.models.jobs import Job
from app.db.session import SessionLocal
from app.integrations.generation.base import (
    GenerationAuthenticationError,
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
        ), {"e": f"pf-{uuid.uuid4().hex}@example.com"}).scalar()
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


def test_auth_error_fails_all_three(
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
    def _fail(self, **_):  # type: ignore[no-untyped-def]
        raise GenerationAuthenticationError("bad key")
    monkeypatch.setattr(OpenAIGenerationProvider, "generate", _fail)

    Worker(worker_id="w-pf")._claim_once()

    with SessionLocal() as db:
        job = db.get(Job, jid)
        run_status = db.execute(text(
            "SELECT status FROM generation_runs "
            "WHERE report_id = :r ORDER BY created_at DESC LIMIT 1"
        ), {"r": rid}).scalar()
        report_status = db.execute(text(
            "SELECT status FROM reports WHERE id = :r"
        ), {"r": rid}).scalar()
    assert job is not None and job.status == "failed"
    assert run_status == "failed"
    assert report_status == "failed"
