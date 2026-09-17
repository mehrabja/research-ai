"""Version failure rolls back the entire success transaction."""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

from app.db.session import SessionLocal
from app.domain.generation import GenerationProviderResult
from app.services.generation import generate_report


def _seed() -> tuple[uuid.UUID, uuid.UUID]:
    with SessionLocal() as db:
        uid = db.execute(text(
            "INSERT INTO users (email, password_hash) "
            "VALUES (:e, 'h') RETURNING id"
        ), {"e": f"at-{uuid.uuid4().hex}@example.com"}).scalar()
        rid = db.execute(text(
            "INSERT INTO reports "
            "(user_id, topic, status, output_language) "
            "VALUES (:u, 'T', 'draft', 'en') RETURNING id"
        ), {"u": uid}).scalar()
        db.commit()
    return uid, rid


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
    def generate(self, **_):  # type: ignore[no-untyped-def]
        return GenerationProviderResult(
            text="ok.", provider=self.provider_name, model=self.model_name,
        )


def test_persistence_rolls_back_on_version_failure(
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    uid, rid = _seed()
    monkeypatch.setattr(
        "app.services.generation.retrieval_service.retrieve",
        lambda *a, **k: ([_rc(rid)], {}),
    )

    def _fail_version(*a, **k):  # type: ignore[no-untyped-def]
        raise RuntimeError("simulated version failure")

    monkeypatch.setattr(
        "app.services.generation.report_versions_service"
        ".create_report_version",
        _fail_version,
    )

    with SessionLocal() as db, pytest.raises(RuntimeError):
        generate_report(
            db, job_id=uuid.uuid4(), user_id=uid, report_id=rid,
            provider=_OkProvider(),
        )

    with SessionLocal() as db:
        assert db.execute(text(
            "SELECT COUNT(*) FROM generation_runs "
            "WHERE report_id = :r AND status = 'success'"
        ), {"r": rid}).scalar() == 0
        assert db.execute(text(
            "SELECT COUNT(*) FROM report_versions WHERE report_id = :r"
        ), {"r": rid}).scalar() == 0
        assert db.execute(text(
            "SELECT COUNT(*) FROM usage_logs "
            "WHERE report_id = :r AND phase = 'generation'"
        ), {"r": rid}).scalar() == 0
