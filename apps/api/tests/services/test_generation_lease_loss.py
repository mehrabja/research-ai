"""Same job_id + already succeeded → GenerationAlreadySucceeded."""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

from app.db.models.jobs import Job
from app.db.session import SessionLocal
from app.domain.generation import (
    GenerationAlreadySucceeded,
    GenerationProviderResult,
)
from app.services.generation import generate_report


def _seed() -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    with SessionLocal() as db:
        uid = db.execute(text(
            "INSERT INTO users (email, password_hash) "
            "VALUES (:e, 'h') RETURNING id"
        ), {"e": f"ll-{uuid.uuid4().hex}@example.com"}).scalar()
        rid = db.execute(text(
            "INSERT INTO reports "
            "(user_id, topic, status, output_language) "
            "VALUES (:u, 'T', 'draft', 'en') RETURNING id"
        ), {"u": uid}).scalar()
        job_id = uuid.uuid4()
        db.add(Job(id=job_id, job_type="generate_report", user_id=uid, report_id=rid))
        db.commit()
    return uid, rid, job_id


def _rc(rid):  # type: ignore[no-untyped-def]
    from app.domain.retrieval import RetrievedChunk
    return RetrievedChunk(
        chunk_id=uuid.uuid4(), source_id=uuid.uuid4(), report_id=rid,
        chunk_index=0, content="ev", char_start=0, char_end=2,
        page_number=None, vector_distance=0.1, vector_similarity=0.9,
        lexical_score=0.5, vector_rank=1, lexical_rank=1,
        fusion_score=0.05, final_rank=1,
    )


class _OkProvider:
    provider_name = "fake"
    model_name = "fake"
    def __init__(self) -> None:
        self.calls = 0
    def generate(self, **_):  # type: ignore[no-untyped-def]
        self.calls += 1
        return GenerationProviderResult(
            text="draft.", provider=self.provider_name,
            model=self.model_name,
        )


def test_second_worker_skips_llm_after_first_success(
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    uid, rid, jid = _seed()
    monkeypatch.setattr(
        "app.services.generation.retrieval_service.retrieve",
        lambda *a, **k: ([_rc(rid)], {}),
    )

    p_a = _OkProvider()
    with SessionLocal() as db:
        generate_report(
            db, job_id=jid, user_id=uid, report_id=rid, provider=p_a,
        )
    assert p_a.calls == 1

    p_b = _OkProvider()
    with SessionLocal() as db, pytest.raises(GenerationAlreadySucceeded):
        generate_report(
            db, job_id=jid, user_id=uid, report_id=rid, provider=p_b,
        )
    assert p_b.calls == 0

    with SessionLocal() as db:
        assert db.execute(text(
            "SELECT COUNT(*) FROM generation_runs WHERE report_id = :r"
        ), {"r": rid}).scalar() == 1
        assert db.execute(text(
            "SELECT COUNT(*) FROM report_versions WHERE report_id = :r"
        ), {"r": rid}).scalar() == 1
        assert db.execute(text(
            "SELECT COUNT(*) FROM usage_logs "
            "WHERE report_id = :r AND phase = 'generation'"
        ), {"r": rid}).scalar() == 1
