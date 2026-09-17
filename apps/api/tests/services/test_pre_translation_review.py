"""M15 — Pre-translation human review service tests."""
from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.core.exceptions import ReportNotFound
from app.db.models.report import Report, ReportEvent, ReportVersion, ReviewEvent
from app.db.models.user import User
from app.db.session import SessionLocal
from app.main import app
from app.services import reviews as reviews_service
from app.services.rate_limit import set_login_rate_limiter

client = TestClient(app)


@pytest.fixture(autouse=True)
def fresh_rate_limiter() -> Iterator[None]:
    set_login_rate_limiter(None)
    yield
    set_login_rate_limiter(None)


@pytest.fixture()
def cleanup_users() -> Iterator[list[uuid.UUID]]:
    user_ids: list[uuid.UUID] = []
    yield user_ids
    if not user_ids:
        return
    with SessionLocal() as db:
        report_ids = select(Report.id).where(Report.user_id.in_(user_ids))
        db.execute(delete(ReviewEvent).where(ReviewEvent.report_id.in_(report_ids)))
        db.execute(delete(ReportEvent).where(ReportEvent.report_id.in_(report_ids)))
        db.execute(delete(ReportVersion).where(ReportVersion.report_id.in_(report_ids)))
        db.execute(delete(Report).where(Report.id.in_(report_ids)))
        db.execute(delete(User).where(User.id.in_(user_ids)))
        db.commit()


def _register(cleanup_users):
    email = f"u-{uuid.uuid4().hex[:12]}@example.com"
    pw = "very-strong-password-1234"
    r = client.post("/api/v1/auth/register", json={"email": email, "password": pw})
    assert r.status_code == 201, r.text
    r = client.post("/api/v1/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    with SessionLocal() as db:
        u = db.execute(select(User).where(User.email == email)).scalar_one()
        cleanup_users.append(u.id)
        return u.id


def _seed(user_id, *, content="Base content."):
    with SessionLocal() as db:
        report = Report(
            user_id=user_id,
            topic="T",
            output_language="en",
            status="pre_translation_review",
        )
        db.add(report)
        db.flush()
        version = ReportVersion(
            report_id=report.id, version_number=1, language="en",
            content=content, created_by_user=False, change_type="humanized",
        )
        db.add(version)
        db.commit()
        return report.id, version.id


# =========================================================================
# get_pre_translation_review
# =========================================================================
def test_get_review_success(cleanup_users):
    uid = _register(cleanup_users)
    report_id, version_id = _seed(uid)

    with SessionLocal() as db:
        data = reviews_service.get_pre_translation_review(
            db, user_id=uid, report_id=report_id
        )
    assert data["report_id"] == report_id
    assert data["version_id"] == version_id
    assert data["status"] == "pre_translation_review"
    assert data["change_type"] == "humanized"
    assert data["review_stage"] == "pre_translation"


def test_get_review_wrong_owner(cleanup_users):
    uid_a = _register(cleanup_users)
    uid_b = _register(cleanup_users)
    report_id, _ = _seed(uid_a)

    with SessionLocal() as db, pytest.raises(ReportNotFound):
        reviews_service.get_pre_translation_review(
            db, user_id=uid_b, report_id=report_id
        )


def test_get_review_invalid_state(cleanup_users):
    uid = _register(cleanup_users)
    with SessionLocal() as db:
        report = Report(
            user_id=uid,
            topic="T",
            output_language="en",
            status="draft",
        )
        db.add(report)
        db.commit()
        report_id = report.id

    with SessionLocal() as db, pytest.raises(reviews_service.InvalidReviewStateError):
        reviews_service.get_pre_translation_review(
            db, user_id=uid, report_id=report_id
        )


# =========================================================================
# edit_pre_translation_review
# =========================================================================
def test_edit_creates_immutable_version(cleanup_users):
    uid = _register(cleanup_users)
    report_id, version_id = _seed(uid)

    with SessionLocal() as db:
        new_v = reviews_service.edit_pre_translation_review(
            db, user_id=uid, report_id=report_id,
            version_id=version_id, content="Edited content.",
        )
        new_v_number = new_v.version_number
        new_v_source = new_v.source_version_id
        new_v_change = new_v.change_type
        new_v_created_by = new_v.created_by_user
        new_v_diff = new_v.diff_from_previous

    assert new_v_number == 2
    assert new_v_source == version_id
    assert new_v_change == "human_review_edit"
    assert new_v_created_by is True
    assert new_v_diff is not None
    assert new_v_diff["type"] == "human_review_edit"

    with SessionLocal() as db:
        old = db.get(ReportVersion, version_id)
        assert old is not None
        assert old.content == "Base content."
        assert old.change_type == "humanized"


def test_edit_creates_event(cleanup_users):
    uid = _register(cleanup_users)
    report_id, version_id = _seed(uid)

    with SessionLocal() as db:
        new_v = reviews_service.edit_pre_translation_review(
            db, user_id=uid, report_id=report_id,
            version_id=version_id, content="Edited.", notes="n",
        )
        new_v_id = new_v.id

    with SessionLocal() as db:
        events = db.execute(
            select(ReviewEvent).where(
                ReviewEvent.report_id == report_id,
                ReviewEvent.action == "edited",
            )
        ).scalars().all()
        assert len(events) == 1
        assert events[0].version_id == new_v_id
        assert events[0].notes == "n"
        assert events[0].user_id == uid


def test_edit_stale_raises(cleanup_users):
    uid = _register(cleanup_users)
    report_id, version_id = _seed(uid)

    with SessionLocal() as db:
        reviews_service.edit_pre_translation_review(
            db, user_id=uid, report_id=report_id,
            version_id=version_id, content="first",
        )

    with SessionLocal() as db, pytest.raises(reviews_service.StaleReviewVersionError):
        reviews_service.edit_pre_translation_review(
            db, user_id=uid, report_id=report_id,
            version_id=version_id, content="stale",
        )


def test_edit_empty_content_raises(cleanup_users):
    uid = _register(cleanup_users)
    report_id, version_id = _seed(uid)

    with SessionLocal() as db, pytest.raises(reviews_service.ReviewValidationError):
        reviews_service.edit_pre_translation_review(
            db, user_id=uid, report_id=report_id,
            version_id=version_id, content="",
        )


# =========================================================================
# approve
# =========================================================================
def test_approve_creates_event_and_transitions(cleanup_users):
    uid = _register(cleanup_users)
    report_id, version_id = _seed(uid)

    with SessionLocal() as db:
        reviews_service.approve_pre_translation_review(
            db, user_id=uid, report_id=report_id, version_id=version_id,
        )

    with SessionLocal() as db:
        report = db.get(Report, report_id)
        assert report.status == "translating"
        events = db.execute(
            select(ReviewEvent).where(
                ReviewEvent.report_id == report_id,
                ReviewEvent.action == "approved",
            )
        ).scalars().all()
        assert len(events) == 1


def test_approve_idempotent_when_already_translating(cleanup_users):
    uid = _register(cleanup_users)
    report_id, version_id = _seed(uid)

    with SessionLocal() as db:
        reviews_service.approve_pre_translation_review(
            db, user_id=uid, report_id=report_id, version_id=version_id,
        )

    with SessionLocal() as db:
        reviews_service.approve_pre_translation_review(
            db, user_id=uid, report_id=report_id, version_id=version_id,
        )

    with SessionLocal() as db:
        events = db.execute(
            select(ReviewEvent).where(
                ReviewEvent.report_id == report_id,
                ReviewEvent.action == "approved",
            )
        ).scalars().all()
        assert len(events) == 1


# =========================================================================
# request_changes / reject
# =========================================================================
def test_request_changes_stays_in_review(cleanup_users):
    uid = _register(cleanup_users)
    report_id, version_id = _seed(uid)

    with SessionLocal() as db:
        reviews_service.request_changes_pre_translation_review(
            db, user_id=uid, report_id=report_id,
            version_id=version_id, notes="n",
        )

    with SessionLocal() as db:
        report = db.get(Report, report_id)
        assert report.status == "pre_translation_review"
        events = db.execute(
            select(ReviewEvent).where(
                ReviewEvent.report_id == report_id,
                ReviewEvent.action == "requested_changes",
            )
        ).scalars().all()
        assert len(events) == 1


def test_reject_stays_in_review(cleanup_users):
    uid = _register(cleanup_users)
    report_id, version_id = _seed(uid)

    with SessionLocal() as db:
        reviews_service.reject_pre_translation_review(
            db, user_id=uid, report_id=report_id,
            version_id=version_id, notes="n",
        )

    with SessionLocal() as db:
        report = db.get(Report, report_id)
        assert report.status == "pre_translation_review"
        events = db.execute(
            select(ReviewEvent).where(
                ReviewEvent.report_id == report_id,
                ReviewEvent.action == "rejected",
            )
        ).scalars().all()
        assert len(events) == 1


# =========================================================================
# Lineage
# =========================================================================
def test_edit_lineage_chain(cleanup_users):
    uid = _register(cleanup_users)
    report_id, v1 = _seed(uid)

    with SessionLocal() as db:
        v2 = reviews_service.edit_pre_translation_review(
            db, user_id=uid, report_id=report_id,
            version_id=v1, content="v2",
        )
        v2_id = v2.id

    with SessionLocal() as db:
        v3 = reviews_service.edit_pre_translation_review(
            db, user_id=uid, report_id=report_id,
            version_id=v2_id, content="v3",
        )
        v3_id = v3.id
        v3_source = v3.source_version_id

    assert v3_source == v2_id
    with SessionLocal() as db:
        assert db.get(ReportVersion, v1).content == "Base content."
        assert db.get(ReportVersion, v2_id).content == "v2"
        assert db.get(ReportVersion, v3_id).content == "v3"
