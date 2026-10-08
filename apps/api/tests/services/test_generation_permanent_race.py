"""A late permanent-failure call must not overwrite generation success.

Regression for the M12 concurrency fix: ``_fail_attempt_and_report``
must lock the GenerationRun row before deciding whether it may
transition it, so that a concurrent success CAS cannot be overwritten
by a stale failure call. Mirrors the semantic pattern of
``tests/services/test_detection_permanent_race.py``.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

from app.core.exceptions import NoEvidenceAvailableError
from app.db.models.pipeline import GenerationRun
from app.db.session import SessionLocal
from app.domain.generation import GenerationProviderResult
from app.services.generation import (
    _fail_attempt_and_report,
    generate_report,
)


def _seed() -> tuple[uuid.UUID, uuid.UUID]:
    with SessionLocal() as db:
        uid = db.execute(
            text(
                "INSERT INTO users (email, password_hash) "
                "VALUES (:e, 'h') RETURNING id"
            ),
            {"e": f"gpr-{uuid.uuid4().hex}@example.com"},
        ).scalar()
        rid = db.execute(
            text(
                "INSERT INTO reports "
                "(user_id, topic, status, output_language) "
                "VALUES (:u, 'T', 'draft', 'en') RETURNING id"
            ),
            {"u": uid},
        ).scalar()
        db.commit()
    return uid, rid


def _rc(rid):  # type: ignore[no-untyped-def]
    from app.domain.retrieval import RetrievedChunk

    return RetrievedChunk(
        chunk_id=uuid.uuid4(),
        source_id=uuid.uuid4(),
        report_id=rid,
        chunk_index=0,
        content="ev",
        char_start=0,
        char_end=2,
        page_number=None,
        vector_distance=0.1,
        vector_similarity=0.9,
        lexical_score=0.5,
        vector_rank=1,
        lexical_rank=1,
        fusion_score=0.05,
        final_rank=1,
    )


class _OkProvider:
    provider_name = "fake"
    model_name = "fake"

    def generate(self, **_):  # type: ignore[no-untyped-def]
        return GenerationProviderResult(
            text="ok.",
            provider=self.provider_name,
            model=self.model_name,
        )


def test_late_failure_does_not_overwrite_success(
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    uid, rid = _seed()
    monkeypatch.setattr(
        "app.services.generation.retrieval_service.retrieve",
        lambda *a, **k: ([_rc(rid)], {}),
    )

    with SessionLocal() as db:
        generate_report(
            db,
            job_id=uuid.uuid4(),
            user_id=uid,
            report_id=rid,
            provider=_OkProvider(),
        )

    with SessionLocal() as db:
        run_id = db.execute(
            text(
                "SELECT id FROM generation_runs "
                "WHERE report_id = :r AND status = 'success' LIMIT 1"
            ),
            {"r": rid},
        ).scalar()
        assert run_id is not None

        _fail_attempt_and_report(
            db,
            attempt_id=run_id,
            user_id=uid,
            report_id=rid,
            error_code="late_error",
        )

    with SessionLocal() as db:
        run_status = db.execute(
            text("SELECT status FROM generation_runs WHERE id = :i"),
            {"i": run_id},
        ).scalar()
        report_status = db.execute(
            text("SELECT status FROM reports WHERE id = :r"),
            {"r": rid},
        ).scalar()
        versions = db.execute(
            text(
                "SELECT COUNT(*) FROM report_versions WHERE report_id = :r"
            ),
            {"r": rid},
        ).scalar()
        usage = db.execute(
            text(
                "SELECT COUNT(*) FROM usage_logs "
                "WHERE report_id = :r AND phase = 'generation'"
            ),
            {"r": rid},
        ).scalar()

    assert run_status == "success"
    assert report_status == "review_1"
    assert versions == 1
    assert usage == 1


def test_late_failure_on_terminal_failed_is_noop(
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    uid, rid = _seed()
    monkeypatch.setattr(
        "app.services.generation.retrieval_service.retrieve",
        lambda *a, **k: ([], {}),
    )

    with SessionLocal() as db, pytest.raises(NoEvidenceAvailableError):
        generate_report(
            db,
            job_id=uuid.uuid4(),
            user_id=uid,
            report_id=rid,
            provider=_OkProvider(),
        )

    with SessionLocal() as db:
        run_id = db.execute(
            text(
                "SELECT id FROM generation_runs "
                "WHERE report_id = :r AND status = 'failed' LIMIT 1"
            ),
            {"r": rid},
        ).scalar()
        assert run_id is not None

        _fail_attempt_and_report(
            db,
            attempt_id=run_id,
            user_id=uid,
            report_id=rid,
            error_code="late_error",
        )

    with SessionLocal() as db:
        run_status = db.execute(
            text("SELECT status FROM generation_runs WHERE id = :i"),
            {"i": run_id},
        ).scalar()
        report_status = db.execute(
            text("SELECT status FROM reports WHERE id = :r"),
            {"r": rid},
        ).scalar()
        run = db.get(GenerationRun, run_id)

    assert run_status == "failed"
    assert report_status == "failed"
    assert run is not None
    assert run.output_json.get("attempt_status") == "failed"
    assert run.output_json.get("error_code") == "no_evidence"
