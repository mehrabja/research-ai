"""Permanent vs retryable failure semantics."""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

from app.db.session import SessionLocal
from app.integrations.detection.base import (
    DetectionAuthenticationError,
    DetectionRateLimitError,
)
from app.services.detection import detect_report_version
from app.services.detection_profile import (
    get_current_detection_profile,
)

_LONG_TEXT = (
    "This is a sufficiently long piece of text. "
    "It contains multiple complete sentences. "
    "Each sentence has several words in it. "
    "The detection provider requires enough characters. "
    "So we pad this text to exceed the minimum. "
    "This ensures the provider path is exercised. "
    "And the label classification is reached. "
    "Finally the test can assert on the outcome."
)


def _seed() -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    with SessionLocal() as db:
        uid = db.execute(
            text(
                "INSERT INTO users (email, password_hash) "
                "VALUES (:e, 'h') RETURNING id"
            ),
            {"e": f"fa-{uuid.uuid4().hex}@example.com"},
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
                "VALUES (:r, 1, 'en', :c) RETURNING id"
            ),
            {"r": rid, "c": _LONG_TEXT},
        ).scalar()
        db.commit()
    return uid, rid, vid


class _AuthFail:
    provider_name = "fail"
    model_name = "fail"

    def detect(self, *, text: str) -> object:
        raise DetectionAuthenticationError("bad")


class _RateLimit:
    provider_name = "rl"
    model_name = "rl"

    def detect(self, *, text: str) -> object:
        raise DetectionRateLimitError("429")


def test_permanent_failure_marks_report_failed() -> None:
    uid, rid, vid = _seed()
    with SessionLocal() as db, pytest.raises(
        DetectionAuthenticationError
    ):
        detect_report_version(
            db,
            user_id=uid,
            report_id=rid,
            version_id=vid,
            provider=_AuthFail(),
            profile=get_current_detection_profile(),
        )
    with SessionLocal() as db:
        report_status = db.execute(
            text("SELECT status FROM reports WHERE id = :r"),
            {"r": rid},
        ).scalar()
        run_status = db.execute(
            text(
                "SELECT status FROM detection_runs WHERE report_id = :r"
            ),
            {"r": rid},
        ).scalar()
    assert report_status == "failed"
    assert run_status == "failed"


def test_retryable_failure_keeps_report_detecting() -> None:
    uid, rid, vid = _seed()
    with SessionLocal() as db, pytest.raises(DetectionRateLimitError):
        detect_report_version(
            db,
            user_id=uid,
            report_id=rid,
            version_id=vid,
            provider=_RateLimit(),
            profile=get_current_detection_profile(),
        )
    with SessionLocal() as db:
        report_status = db.execute(
            text("SELECT status FROM reports WHERE id = :r"),
            {"r": rid},
        ).scalar()
        run_status = db.execute(
            text(
                "SELECT status FROM detection_runs WHERE report_id = :r"
            ),
            {"r": rid},
        ).scalar()
    assert report_status == "detecting"
    assert run_status == "running"
