"""Empty retrieval → NoEvidenceAvailableError, run/report → failed."""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

from app.core.exceptions import NoEvidenceAvailableError
from app.db.session import SessionLocal
from app.services.generation import generate_report


def _seed() -> tuple[uuid.UUID, uuid.UUID]:
    with SessionLocal() as db:
        uid = db.execute(text(
            "INSERT INTO users (email, password_hash) "
            "VALUES (:e, 'h') RETURNING id"
        ), {"e": f"ne-{uuid.uuid4().hex}@example.com"}).scalar()
        rid = db.execute(text(
            "INSERT INTO reports "
            "(user_id, topic, status, output_language) "
            "VALUES (:u, 'T', 'draft', 'en') RETURNING id"
        ), {"u": uid}).scalar()
        db.commit()
    return uid, rid


class _SpyProvider:
    provider_name = "spy"
    model_name = "spy"
    def generate(self, **_):  # type: ignore[no-untyped-def]
        raise AssertionError("provider must not be called")


def test_no_evidence_marks_attempt_and_report_failed(
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    uid, rid = _seed()
    monkeypatch.setattr(
        "app.services.generation.retrieval_service.retrieve",
        lambda *a, **k: ([], {}),
    )
    with SessionLocal() as db, pytest.raises(NoEvidenceAvailableError):
        generate_report(
            db, job_id=uuid.uuid4(), user_id=uid, report_id=rid,
            provider=_SpyProvider(),
        )
    with SessionLocal() as db:
        run_status = db.execute(text(
            "SELECT status FROM generation_runs "
            "WHERE report_id = :r ORDER BY created_at DESC LIMIT 1"
        ), {"r": rid}).scalar()
        report_status = db.execute(text(
            "SELECT status FROM reports WHERE id = :r"
        ), {"r": rid}).scalar()
    assert run_status == "failed"
    assert report_status == "failed"
