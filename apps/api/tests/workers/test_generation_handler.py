"""Handler-level tests for generate_report."""
from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from sqlalchemy import text

from app.db.session import SessionLocal
from app.domain.jobs import JobContext


def _mk_job() -> tuple[uuid.UUID, uuid.UUID]:
    with SessionLocal() as db:
        uid = db.execute(text(
            "INSERT INTO users (email, password_hash) "
            "VALUES (:e, 'h') RETURNING id"
        ), {"e": f"gh-{uuid.uuid4().hex}@example.com"}).scalar()
        rid = db.execute(text(
            "INSERT INTO reports "
            "(user_id, topic, status, output_language) "
            "VALUES (:u, 'T', 'draft', 'en') RETURNING id"
        ), {"u": uid}).scalar()
        jid = db.execute(text(
            "INSERT INTO jobs "
            "(job_type, status, payload, user_id, report_id, "
            " attempt_count, max_attempts, worker_id, "
            " heartbeat_at, started_at) "
            "VALUES ('generate_report', 'processing', "
            "        CAST(:p AS jsonb), :u, :r, 1, 3, 'w-test', "
            "        now(), now()) RETURNING id"
        ), {
            "p": f'{{"report_id":"{rid}"}}',
            "u": uid,
            "r": rid,
        }).scalar()
        db.commit()
    return jid, rid


def _ctx(job_id: uuid.UUID, report_id: uuid.UUID) -> JobContext:
    return JobContext(
        job_id=job_id, job_type="generate_report",
        attempt_count=1, worker_id="w-test",
        payload={"report_id": str(report_id), "brief": "focus on limitations"},
    )


def test_missing_report_id_raises() -> None:
    from app.workers.handlers import (
        InvalidGenerationPayloadError,
        _generate_report,
    )
    ctx = JobContext(
        job_id=uuid.uuid4(), job_type="generate_report",
        attempt_count=1, worker_id="w-test", payload={},
    )
    with pytest.raises(InvalidGenerationPayloadError):
        _generate_report(ctx)


def test_valid_payload_calls_service() -> None:
    from app.domain.generation import (
        EvidenceSet,
        GenerationProviderResult,
        GenerationResult,
    )
    from app.workers.handlers import _generate_report
    jid, rid = _mk_job()
    ctx = _ctx(jid, rid)
    fake = GenerationResult(
        text="draft", language="en", profile_id="p",
        evidence=EvidenceSet(items=()), cited_markers=(),
        provider_result=GenerationProviderResult(
            text="draft", provider="fake", model="fake",
        ),
    )
    with patch(
        "app.workers.handlers.generation_service.generate_report",
        return_value=fake,
    ) as m:
        _generate_report(ctx)
    assert m.call_count == 1
    assert m.call_args.kwargs["brief"] == "focus on limitations"
