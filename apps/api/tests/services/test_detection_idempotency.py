"""Second identical detection raises DetectionAlreadyCompletedError."""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

from app.core.exceptions import DetectionAlreadyCompletedError
from app.db.session import SessionLocal
from app.integrations.detection.heuristic import (
    HeuristicDetectionProvider,
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
            {"e": f"idp-{uuid.uuid4().hex}@example.com"},
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


def test_second_detection_raises_already_completed() -> None:
    uid, rid, vid = _seed()
    profile = get_current_detection_profile()

    with SessionLocal() as db:
        detect_report_version(
            db,
            user_id=uid,
            report_id=rid,
            version_id=vid,
            provider=HeuristicDetectionProvider(),
            profile=profile,
        )
    with SessionLocal() as db, pytest.raises(
        DetectionAlreadyCompletedError
    ):
        detect_report_version(
            db,
            user_id=uid,
            report_id=rid,
            version_id=vid,
            provider=HeuristicDetectionProvider(),
            profile=profile,
        )
