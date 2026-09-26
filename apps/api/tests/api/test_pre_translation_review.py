"""M15 — Pre-translation human review API tests."""
from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.db.models.report import Report, ReportEvent, ReportVersion, ReviewEvent
from app.db.models.user import User
from app.db.models.workspace import Workspace
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
        db.execute(delete(ReviewEvent).where(ReviewEvent.report_id.in_(report_ids)))
        db.execute(delete(ReportEvent).where(ReportEvent.report_id.in_(report_ids)))
        db.execute(delete(ReportVersion).where(ReportVersion.report_id.in_(report_ids)))
        db.execute(delete(Report).where(Report.id.in_(report_ids)))
        # M37: purge owned workspaces before deleting user
        db.execute(
            delete(Workspace).where(
                Workspace.owner_user_id.in_(user_ids)
            )
        )
        db.execute(delete(User).where(User.id.in_(user_ids)))
        db.commit()


def _register_and_login(cleanup_users: list[uuid.UUID]) -> tuple[uuid.UUID, str]:
    email = f"user-{uuid.uuid4().hex[:12]}@example.com"
    password = "very-strong-password-1234"
    r = client.post("/api/v1/auth/register", json={"email": email, "password": password})
    assert r.status_code == 201, r.text
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    with SessionLocal() as db:
        user = db.execute(select(User).where(User.email == email)).scalar_one()
        cleanup_users.append(user.id)
        return user.id, token


def _seed_reviewable(
    user_id: uuid.UUID, *, content: str = "Original humanized content."
) -> tuple[uuid.UUID, uuid.UUID]:
    with SessionLocal() as db:
        report = Report(
            user_id=user_id,
            topic="Test topic",
            output_language="en",
            status="pre_translation_review",
        )
        db.add(report)
        db.flush()
        version = ReportVersion(
            report_id=report.id,
            version_number=1,
            language="en",
            content=content,
            created_by_user=False,
            change_type="humanized",
        )
        db.add(version)
        db.commit()
        return report.id, version.id


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# =========================================================================
# GET
# =========================================================================
def test_get_review_success(cleanup_users):
    uid, token = _register_and_login(cleanup_users)
    report_id, version_id = _seed_reviewable(uid)

    r = client.get(
        f"/api/v1/reports/{report_id}/review/pre-translation",
        headers=_auth(token),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["report_id"] == str(report_id)
    assert body["version_id"] == str(version_id)
    assert body["status"] == "pre_translation_review"
    assert body["change_type"] == "humanized"
    assert body["review_stage"] == "pre_translation"
    assert body["review_events"] == []


def test_get_review_wrong_owner_404(cleanup_users):
    uid_a, _ = _register_and_login(cleanup_users)
    _, token_b = _register_and_login(cleanup_users)
    report_id, _ = _seed_reviewable(uid_a)

    r = client.get(
        f"/api/v1/reports/{report_id}/review/pre-translation",
        headers=_auth(token_b),
    )
    assert r.status_code == 404


def test_get_review_wrong_status_409(cleanup_users):
    uid, token = _register_and_login(cleanup_users)
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

    r = client.get(
        f"/api/v1/reports/{report_id}/review/pre-translation",
        headers=_auth(token),
    )
    assert r.status_code == 409


# =========================================================================
# Edit
# =========================================================================
def test_edit_creates_new_version(cleanup_users):
    uid, token = _register_and_login(cleanup_users)
    report_id, version_id = _seed_reviewable(uid)

    r = client.post(
        f"/api/v1/reports/{report_id}/review/pre-translation/edit",
        json={"version_id": str(version_id), "content": "Edited text."},
        headers=_auth(token),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["content"] == "Edited text."
    assert body["version_id"] != str(version_id)

    with SessionLocal() as db:
        old = db.get(ReportVersion, version_id)
        assert old is not None
        assert old.content == "Original humanized content."
        new = db.get(ReportVersion, uuid.UUID(body["version_id"]))
        assert new is not None
        assert new.change_type == "human_review_edit"
        assert new.created_by_user is True
        assert new.source_version_id == version_id
        assert new.diff_from_previous is not None
        assert new.diff_from_previous["type"] == "human_review_edit"


def test_edit_creates_review_event(cleanup_users):
    uid, token = _register_and_login(cleanup_users)
    report_id, version_id = _seed_reviewable(uid)

    r = client.post(
        f"/api/v1/reports/{report_id}/review/pre-translation/edit",
        json={"version_id": str(version_id), "content": "Edited.", "notes": "fix intro"},
        headers=_auth(token),
    )
    assert r.status_code == 200, r.text

    with SessionLocal() as db:
        events = db.execute(
            select(ReviewEvent).where(
                ReviewEvent.report_id == report_id,
                ReviewEvent.stage == "pre_translation",
                ReviewEvent.action == "edited",
            )
        ).scalars().all()
        assert len(events) == 1
        assert events[0].notes == "fix intro"
        assert events[0].user_id == uid


def test_edit_stale_version_409(cleanup_users):
    uid, token = _register_and_login(cleanup_users)
    report_id, version_id = _seed_reviewable(uid)

    r = client.post(
        f"/api/v1/reports/{report_id}/review/pre-translation/edit",
        json={"version_id": str(version_id), "content": "first edit"},
        headers=_auth(token),
    )
    assert r.status_code == 200

    r2 = client.post(
        f"/api/v1/reports/{report_id}/review/pre-translation/edit",
        json={"version_id": str(version_id), "content": "stale edit"},
        headers=_auth(token),
    )
    assert r2.status_code == 409
    assert "STALE_REVIEW_VERSION" in r2.text or "stale" in r2.text.lower()


def test_edit_empty_content_422(cleanup_users):
    uid, token = _register_and_login(cleanup_users)
    report_id, version_id = _seed_reviewable(uid)

    r = client.post(
        f"/api/v1/reports/{report_id}/review/pre-translation/edit",
        json={"version_id": str(version_id), "content": ""},
        headers=_auth(token),
    )
    assert r.status_code == 422


# =========================================================================
# Approve
# =========================================================================
def test_approve_transitions_to_translating(cleanup_users):
    uid, token = _register_and_login(cleanup_users)
    report_id, version_id = _seed_reviewable(uid)

    r = client.post(
        f"/api/v1/reports/{report_id}/review/pre-translation/approve",
        json={"version_id": str(version_id)},
        headers=_auth(token),
    )
    assert r.status_code == 200, r.text

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


def test_approve_idempotent(cleanup_users):
    uid, token = _register_and_login(cleanup_users)
    report_id, version_id = _seed_reviewable(uid)

    r1 = client.post(
        f"/api/v1/reports/{report_id}/review/pre-translation/approve",
        json={"version_id": str(version_id)},
        headers=_auth(token),
    )
    assert r1.status_code == 200

    r2 = client.post(
        f"/api/v1/reports/{report_id}/review/pre-translation/approve",
        json={"version_id": str(version_id)},
        headers=_auth(token),
    )
    assert r2.status_code == 200

    with SessionLocal() as db:
        events = db.execute(
            select(ReviewEvent).where(
                ReviewEvent.report_id == report_id,
                ReviewEvent.action == "approved",
            )
        ).scalars().all()
        assert len(events) == 1


def test_approve_stale_version_409(cleanup_users):
    uid, token = _register_and_login(cleanup_users)
    report_id, version_id = _seed_reviewable(uid)

    r = client.post(
        f"/api/v1/reports/{report_id}/review/pre-translation/edit",
        json={"version_id": str(version_id), "content": "new text"},
        headers=_auth(token),
    )
    assert r.status_code == 200

    r2 = client.post(
        f"/api/v1/reports/{report_id}/review/pre-translation/approve",
        json={"version_id": str(version_id)},
        headers=_auth(token),
    )
    assert r2.status_code == 409


# =========================================================================
# Request changes
# =========================================================================
def test_request_changes_stays_in_review(cleanup_users):
    uid, token = _register_and_login(cleanup_users)
    report_id, version_id = _seed_reviewable(uid)

    r = client.post(
        f"/api/v1/reports/{report_id}/review/pre-translation/request-changes",
        json={"version_id": str(version_id), "notes": "please simplify"},
        headers=_auth(token),
    )
    assert r.status_code == 200, r.text

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
        assert events[0].notes == "please simplify"


def test_request_changes_empty_notes_422(cleanup_users):
    uid, token = _register_and_login(cleanup_users)
    report_id, version_id = _seed_reviewable(uid)

    r = client.post(
        f"/api/v1/reports/{report_id}/review/pre-translation/request-changes",
        json={"version_id": str(version_id), "notes": ""},
        headers=_auth(token),
    )
    assert r.status_code == 422


# =========================================================================
# Reject
# =========================================================================
def test_reject_stays_in_review(cleanup_users):
    uid, token = _register_and_login(cleanup_users)
    report_id, version_id = _seed_reviewable(uid)

    r = client.post(
        f"/api/v1/reports/{report_id}/review/pre-translation/reject",
        json={"version_id": str(version_id), "notes": "not acceptable"},
        headers=_auth(token),
    )
    assert r.status_code == 200, r.text

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
# Ownership
# =========================================================================
def test_edit_wrong_owner_404(cleanup_users):
    uid_a, _ = _register_and_login(cleanup_users)
    _, token_b = _register_and_login(cleanup_users)
    report_id, version_id = _seed_reviewable(uid_a)

    r = client.post(
        f"/api/v1/reports/{report_id}/review/pre-translation/edit",
        json={"version_id": str(version_id), "content": "attack"},
        headers=_auth(token_b),
    )
    assert r.status_code == 404


def test_approve_wrong_owner_404(cleanup_users):
    uid_a, _ = _register_and_login(cleanup_users)
    _, token_b = _register_and_login(cleanup_users)
    report_id, version_id = _seed_reviewable(uid_a)

    r = client.post(
        f"/api/v1/reports/{report_id}/review/pre-translation/approve",
        json={"version_id": str(version_id)},
        headers=_auth(token_b),
    )
    assert r.status_code == 404
