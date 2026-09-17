"""A late permanent-failure call must not overwrite success."""
from __future__ import annotations

import uuid

from sqlalchemy import text

from app.db.session import SessionLocal
from app.integrations.detection.heuristic import (
    HeuristicDetectionProvider,
)
from app.services.detection import (
    _fail_attempt_and_report,
    detect_report_version,
)
from app.services.detection_profile import (
    get_current_detection_profile,
)


def _seed() -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    with SessionLocal() as db:
        uid = db.execute(
            text(
                "INSERT INTO users (email, password_hash) "
                "VALUES (:e, 'h') RETURNING id"
            ),
            {"e": f"pr-{uuid.uuid4().hex}@example.com"},
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
                "VALUES (:r, 1, 'en', "
                "'Alpha. Beta. Gamma. Delta. Epsilon.') "
                "RETURNING id"
            ),
            {"r": rid},
        ).scalar()
        db.commit()
    return uid, rid, vid


def test_late_failure_does_not_overwrite_success() -> None:
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

    with SessionLocal() as db:
        run = db.execute(
            text(
                "SELECT id FROM detection_runs "
                "WHERE report_id = :r AND status = 'completed' "
                "LIMIT 1"
            ),
            {"r": rid},
        ).scalar()
        assert run is not None
        _fail_attempt_and_report(
            db,
            attempt_id=run,
            user_id=uid,
            report_id=rid,
            error_code="late_error",
        )

    with SessionLocal() as db:
        status = db.execute(
            text("SELECT status FROM detection_runs WHERE id = :i"),
            {"i": run},
        ).scalar()
        report_status = db.execute(
            text("SELECT status FROM reports WHERE id = :r"),
            {"r": rid},
        ).scalar()
    assert status == "completed"
    assert report_status == "humanizing"
