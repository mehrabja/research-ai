"""Detection service happy-path tests."""
from __future__ import annotations

import uuid

from sqlalchemy import text

from app.db.session import SessionLocal
from app.integrations.detection.heuristic import (
    HeuristicDetectionProvider,
)
from app.services.detection import detect_report_version
from app.services.detection_profile import (
    get_current_detection_profile,
)

# Must exceed detection_minimum_text_chars (default 200) so the
# provider path is actually exercised.
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
            {"e": f"dt-{uuid.uuid4().hex}@example.com"},
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


def test_successful_detection_transitions_to_humanizing() -> None:
    uid, rid, vid = _seed()
    with SessionLocal() as db:
        result = detect_report_version(
            db,
            user_id=uid,
            report_id=rid,
            version_id=vid,
            provider=HeuristicDetectionProvider(),
            profile=get_current_detection_profile(),
        )
    assert result.probability is not None
    assert result.label in ("low", "medium", "high", "unknown")

    with SessionLocal() as db:
        report_status = db.execute(
            text("SELECT status FROM reports WHERE id = :r"),
            {"r": rid},
        ).scalar()
        run_status = db.execute(
            text(
                "SELECT status FROM detection_runs "
                "WHERE report_id = :r AND version_id = :v"
            ),
            {"r": rid, "v": vid},
        ).scalar()
    assert report_status == "humanizing"
    assert run_status == "completed"


def test_report_version_content_unchanged() -> None:
    uid, rid, vid = _seed()
    with SessionLocal() as db:
        before = db.execute(
            text("SELECT content FROM report_versions WHERE id = :v"),
            {"v": vid},
        ).scalar()
    with SessionLocal() as db:
        detect_report_version(
            db,
            user_id=uid,
            report_id=rid,
            version_id=vid,
            provider=HeuristicDetectionProvider(),
            profile=get_current_detection_profile(),
        )
    with SessionLocal() as db:
        after = db.execute(
            text("SELECT content FROM report_versions WHERE id = :v"),
            {"v": vid},
        ).scalar()
        versions = db.execute(
            text(
                "SELECT COUNT(*) FROM report_versions "
                "WHERE report_id = :r"
            ),
            {"r": rid},
        ).scalar()
    assert before == after
    assert versions == 1
