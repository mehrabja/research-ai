"""Generation service with mocked provider."""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

from app.db.models.jobs import Job
from app.db.models.pipeline import GenerationRun
from app.db.session import SessionLocal
from app.domain.generation import (
    EmptyGenerationError,
    GenerationProviderResult,
    UnknownEvidenceMarkerError,
)
from app.services.generation import generate_report


def _mk_user() -> uuid.UUID:
    with SessionLocal() as db:
        uid = db.execute(text(
            "INSERT INTO users (email, password_hash) "
            "VALUES (:e, 'h') RETURNING id"
        ), {"e": f"gen-{uuid.uuid4().hex}@example.com"}).scalar()
        db.commit()
    return uid


def _mk_report(*, uid: uuid.UUID, topic: str = "T") -> uuid.UUID:
    with SessionLocal() as db:
        rid = db.execute(text(
            "INSERT INTO reports "
            "(user_id, topic, status, output_language) "
            "VALUES (:u, :t, 'draft', 'en') RETURNING id"
        ), {"u": uid, "t": topic}).scalar()
        db.commit()
    return rid


def _mk_job(*, uid: uuid.UUID, rid: uuid.UUID) -> uuid.UUID:
    job_id = uuid.uuid4()
    with SessionLocal() as db:
        db.add(
            Job(
                id=job_id,
                job_type="generate_report",
                user_id=uid,
                report_id=rid,
            )
        )
        db.commit()
    return job_id


def _rc(rid):  # type: ignore[no-untyped-def]
    from app.domain.retrieval import RetrievedChunk
    return RetrievedChunk(
        chunk_id=uuid.uuid4(), source_id=uuid.uuid4(), report_id=rid,
        chunk_index=0, content="ev", char_start=0, char_end=2,
        page_number=None, vector_distance=0.1, vector_similarity=0.9,
        lexical_score=0.5, vector_rank=1, lexical_rank=1,
        fusion_score=0.05, final_rank=1,
    )


class _FakeProvider:
    provider_name = "fake"
    model_name = "fake-model"
    def __init__(self, *, text: str) -> None:
        self._text = text
    def generate(self, **_):  # type: ignore[no-untyped-def]
        return GenerationProviderResult(
            text=self._text, provider=self.provider_name,
            model=self.model_name, input_tokens=1, output_tokens=1,
        )


def test_success_no_markers(monkeypatch) -> None:
    uid = _mk_user()
    rid = _mk_report(uid=uid)
    monkeypatch.setattr(
        "app.services.generation.retrieval_service.retrieve",
        lambda *a, **k: ([_rc(rid)], {}),
    )
    with SessionLocal() as db:
        r = generate_report(
            db, job_id=_mk_job(uid=uid, rid=rid), user_id=uid, report_id=rid,
            provider=_FakeProvider(text="A short draft."),
        )
    assert r.text == "A short draft."
    assert r.cited_markers == ()

    with SessionLocal() as db:
        run = db.query(GenerationRun).filter(
            GenerationRun.report_id == rid
        ).order_by(GenerationRun.created_at.desc()).first()
        assert run is not None
        assert run.status == "success"
        assert isinstance(run.output_json.get("context_hash"), str)
        assert len(run.output_json["context_hash"]) == 64


def test_empty_output_rejected(monkeypatch) -> None:
    uid = _mk_user()
    rid = _mk_report(uid=uid)
    monkeypatch.setattr(
        "app.services.generation.retrieval_service.retrieve",
        lambda *a, **k: ([_rc(rid)], {}),
    )
    with SessionLocal() as db, pytest.raises(EmptyGenerationError):
        generate_report(
            db, job_id=_mk_job(uid=uid, rid=rid), user_id=uid, report_id=rid,
            provider=_FakeProvider(text="   "),
        )


def test_unknown_marker_rejected(monkeypatch) -> None:
    uid = _mk_user()
    rid = _mk_report(uid=uid)
    monkeypatch.setattr(
        "app.services.generation.retrieval_service.retrieve",
        lambda *a, **k: ([_rc(rid)], {}),
    )
    with SessionLocal() as db, pytest.raises(UnknownEvidenceMarkerError):
        generate_report(
            db, job_id=_mk_job(uid=uid, rid=rid), user_id=uid, report_id=rid,
            provider=_FakeProvider(text="claim [E99]"),
        )
