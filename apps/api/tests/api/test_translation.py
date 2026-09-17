"""M16 — Translation API tests."""
from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.db.models.jobs import Job
from app.db.models.ops import UsageLog
from app.db.models.pipeline import TranslationRun, TranslationVersion
from app.db.models.report import Report, ReportEvent, ReportVersion, ReviewEvent
from app.db.models.user import User
from app.db.session import SessionLocal
from app.main import app
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
        run_ids = select(TranslationRun.id).where(
            TranslationRun.report_id.in_(report_ids)
        )
        db.execute(
            delete(UsageLog).where(UsageLog.report_id.in_(report_ids))
        )
        db.execute(
            delete(TranslationVersion).where(
                TranslationVersion.translation_run_id.in_(run_ids)
            )
        )
        db.execute(
            delete(TranslationRun).where(
                TranslationRun.report_id.in_(report_ids)
            )
        )
        db.execute(delete(Job).where(Job.report_id.in_(report_ids)))
        db.execute(
            delete(ReviewEvent).where(ReviewEvent.report_id.in_(report_ids))
        )
        db.execute(
            delete(ReportEvent).where(ReportEvent.report_id.in_(report_ids))
        )
        db.execute(
            delete(ReportVersion).where(
                ReportVersion.report_id.in_(report_ids)
            )
        )
        db.execute(delete(Report).where(Report.id.in_(report_ids)))
        db.execute(delete(User).where(User.id.in_(user_ids)))
        db.commit()


def _register_and_login(cleanup_users):
    email = f"user-{uuid.uuid4().hex[:12]}@example.com"
    pw = "very-strong-password-1234"
    r = client.post(
        "/api/v1/auth/register", json={"email": email, "password": pw}
    )
    assert r.status_code == 201, r.text
    r = client.post(
        "/api/v1/auth/login", json={"email": email, "password": pw}
    )
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    with SessionLocal() as db:
        u = db.execute(select(User).where(User.email == email)).scalar_one()
        cleanup_users.append(u.id)
        return u.id, token


def _seed_approved(uid, *, report_status: str = "translating"):
    with SessionLocal() as db:
        report = Report(
            user_id=uid,
            topic="T",
            output_language="fa",
            status=report_status,
        )
        db.add(report)
        db.flush()
        v = ReportVersion(
            report_id=report.id,
            version_number=1,
            language="en",
            content="Hello [E1] world 42%.",
            created_by_user=False,
            change_type="humanized",
        )
        db.add(v)
        db.flush()
        db.add(
            ReviewEvent(
                report_id=report.id,
                stage="pre_translation",
                user_id=uid,
                action="approved",
                version_id=v.id,
                notes=None,
            )
        )
        db.commit()
        return report.id, v.id


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_enqueue_translation_success(cleanup_users):
    uid, token = _register_and_login(cleanup_users)
    report_id, version_id = _seed_approved(uid)

    r = client.post(
        f"/api/v1/reports/{report_id}/translation/enqueue",
        json={
            "source_version_id": str(version_id),
            "target_language": "fa",
        },
        headers=_auth(token),
    )
    assert r.status_code == 202, r.text
    body = r.json()
    assert body["status"] == "queued"
    uuid.UUID(body["job_id"])


def test_enqueue_wrong_owner_404(cleanup_users):
    uid_a, _ = _register_and_login(cleanup_users)
    _, token_b = _register_and_login(cleanup_users)
    report_id, version_id = _seed_approved(uid_a)

    r = client.post(
        f"/api/v1/reports/{report_id}/translation/enqueue",
        json={
            "source_version_id": str(version_id),
            "target_language": "fa",
        },
        headers=_auth(token_b),
    )
    assert r.status_code == 404


def test_enqueue_wrong_status_409(cleanup_users):
    uid, token = _register_and_login(cleanup_users)
    report_id, version_id = _seed_approved(
        uid, report_status="pre_translation_review"
    )

    r = client.post(
        f"/api/v1/reports/{report_id}/translation/enqueue",
        json={
            "source_version_id": str(version_id),
            "target_language": "fa",
        },
        headers=_auth(token),
    )
    assert r.status_code == 409


def test_enqueue_wrong_version_409(cleanup_users):
    uid, token = _register_and_login(cleanup_users)
    report_id, version_id = _seed_approved(uid)

    with SessionLocal() as db:
        v2 = ReportVersion(
            report_id=report_id,
            version_number=2,
            language="en",
            content="Unapproved.",
            created_by_user=True,
            change_type="human_review_edit",
        )
        db.add(v2)
        db.commit()
        v2_id = v2.id

    r = client.post(
        f"/api/v1/reports/{report_id}/translation/enqueue",
        json={
            "source_version_id": str(v2_id),
            "target_language": "fa",
        },
        headers=_auth(token),
    )
    assert r.status_code == 409


def test_enqueue_foreign_version_404(cleanup_users):
    uid_a, _ = _register_and_login(cleanup_users)
    uid_b, token_b = _register_and_login(cleanup_users)
    _report_a, ver_a = _seed_approved(uid_a)
    report_b, _ver_b = _seed_approved(uid_b)

    r = client.post(
        f"/api/v1/reports/{report_b}/translation/enqueue",
        json={
            "source_version_id": str(ver_a),
            "target_language": "fa",
        },
        headers=_auth(token_b),
    )
    assert r.status_code == 404
