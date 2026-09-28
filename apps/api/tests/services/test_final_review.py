"""M17/M18 — Final review service tests."""
from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import delete, select

from app.db.models.report import Report, ReportEvent, ReportVersion, ReviewEvent
from app.db.models.user import User
from app.db.models.workspace import Workspace
from app.db.session import SessionLocal
from app.services import reviews as reviews_service
from app.services.rate_limit import set_login_rate_limiter
from app.main import app  # noqa: F401
from fastapi.testclient import TestClient

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
        db.execute(delete(Workspace).where(Workspace.owner_user_id.in_(user_ids)))
        db.execute(delete(User).where(User.id.in_(user_ids)))
        db.commit()


def _register(cleanup_users) -> uuid.UUID:
    email = f"final-{uuid.uuid4().hex[:12]}@example.com"
    password = "very-strong-password-1234"
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password},
    )
    assert response.status_code == 201, response.text
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200, response.text
    with SessionLocal() as db:
        user = db.execute(select(User).where(User.email == email)).scalar_one()
        cleanup_users.append(user.id)
        return user.id


def _seed(user_id: uuid.UUID) -> tuple[uuid.UUID, uuid.UUID]:
    with SessionLocal() as db:
        report = Report(
            user_id=user_id,
            topic="Final",
            output_language="en",
            status="review_2",
        )
        db.add(report)
        db.flush()
        version = ReportVersion(
            report_id=report.id,
            version_number=1,
            language="en",
            content="Humanized translated content.",
            created_by_user=False,
            change_type="humanized_post_translation",
        )
        db.add(version)
        db.commit()
        return report.id, version.id


def test_final_review_edit_preserves_lineage(cleanup_users):
    uid = _register(cleanup_users)
    report_id, version_id = _seed(uid)

    with SessionLocal() as db:
        edited = reviews_service.edit_final_review(
            db,
            user_id=uid,
            report_id=report_id,
            version_id=version_id,
            content="Final edited content.",
            notes="clarify wording",
        )

    assert edited.version_number == 2
    assert edited.source_version_id == version_id
    assert edited.change_type == "human_review_edit"

    with SessionLocal() as db:
        event = db.execute(
            select(ReviewEvent).where(
                ReviewEvent.report_id == report_id,
                ReviewEvent.stage == "post_translation",
                ReviewEvent.action == "edited",
            )
        ).scalar_one()
        assert event.version_id == edited.id
        assert event.notes == "clarify wording"


def test_final_review_request_changes_and_reject_stay_in_review(cleanup_users):
    uid = _register(cleanup_users)
    report_id, version_id = _seed(uid)

    with SessionLocal() as db:
        reviews_service.request_changes_final_review(
            db,
            user_id=uid,
            report_id=report_id,
            version_id=version_id,
            notes="adjust terminology",
        )

    with SessionLocal() as db:
        reviews_service.reject_final_review(
            db,
            user_id=uid,
            report_id=report_id,
            version_id=version_id,
            notes="reject for revision",
        )

    with SessionLocal() as db:
        report = db.get(Report, report_id)
        assert report is not None
        assert report.status == "review_2"
        actions = list(
            db.execute(
                select(ReviewEvent.action).where(
                    ReviewEvent.report_id == report_id,
                    ReviewEvent.stage == "post_translation",
                )
            ).scalars().all()
        )
        assert actions == ["requested_changes", "rejected"]


def test_final_review_approve_moves_to_validation(cleanup_users):
    uid = _register(cleanup_users)
    report_id, version_id = _seed(uid)

    with SessionLocal() as db:
        reviews_service.approve_final_review(
            db,
            user_id=uid,
            report_id=report_id,
            version_id=version_id,
        )

    with SessionLocal() as db:
        report = db.get(Report, report_id)
        assert report is not None
        assert report.status == "validating"
        event = db.execute(
            select(ReviewEvent).where(
                ReviewEvent.report_id == report_id,
                ReviewEvent.stage == "post_translation",
                ReviewEvent.action == "approved",
            )
        ).scalar_one()
        assert event.version_id == version_id


def test_final_review_requires_review_2(cleanup_users):
    uid = _register(cleanup_users)
    with SessionLocal() as db:
        report = Report(
            user_id=uid,
            topic="Not ready",
            output_language="en",
            status="converging",
        )
        db.add(report)
        db.commit()
        report_id = report.id

    with SessionLocal() as db, pytest.raises(reviews_service.InvalidReviewStateError):
        reviews_service.get_final_review(db, user_id=uid, report_id=report_id)
