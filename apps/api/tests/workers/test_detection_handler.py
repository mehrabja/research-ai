"""Worker handler dispatch for detect_report."""
from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from sqlalchemy import text

from app.db.session import SessionLocal
from app.domain.jobs import JobContext
from app.workers.handlers import (
    InvalidDetectionPayloadError,
    _detect_report,
)


def test_missing_version_id_raises() -> None:
    ctx = JobContext(
        job_id=uuid.uuid4(),
        job_type="detect_report",
        attempt_count=1,
        worker_id="w-test",
        payload={"report_id": str(uuid.uuid4())},
    )
    with pytest.raises(InvalidDetectionPayloadError):
        _detect_report(ctx)


def test_valid_payload_calls_service() -> None:
    from app.services import detection_jobs

    with SessionLocal() as db:
        uid = db.execute(
            text(
                "INSERT INTO users (email, password_hash) "
                "VALUES (:e, 'h') RETURNING id"
            ),
            {"e": f"dth-{uuid.uuid4().hex}@example.com"},
        ).scalar()
        rid = db.execute(
            text(
                "INSERT INTO reports "
                "(user_id, topic, status, output_language) "
                "VALUES (:u, 'T', 'review_1', 'en') RETURNING id"
            ),
            {"u": uid},
        ).scalar()
        vid = db.execute(
            text(
                "INSERT INTO report_versions "
                "(report_id, version_number, language, content) "
                "VALUES (:r, 1, 'en', 'x') RETURNING id"
            ),
            {"r": rid},
        ).scalar()
        db.commit()

        result = detection_jobs.enqueue_detection_job(
            db,
            user_id=uid,
            report_id=rid,
            version_id=vid,
        )
        jid = result.job.id

    ctx = JobContext(
        job_id=jid,
        job_type="detect_report",
        attempt_count=1,
        worker_id="w-test",
        payload={"report_id": str(rid), "version_id": str(vid)},
    )
    with patch(
        "app.workers.handlers.detection_service.detect_report_version"
    ) as m:
        m.return_value = type(
            "R", (), {"label": "medium", "probability": 0.5}
        )()
        _detect_report(ctx)
    assert m.call_count == 1
