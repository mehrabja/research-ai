"""Detection API tests (enqueue + read)."""
from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import bindparam, delete, text

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


def _delete_children_for_users(
    db,
    table: str,
    user_ids: list[uuid.UUID],
) -> None:
    stmt = text(
        f"DELETE FROM {table} WHERE report_id IN "
        "(SELECT id FROM reports WHERE user_id IN :ids)"
    ).bindparams(bindparam("ids", expanding=True))
    db.execute(stmt, {"ids": user_ids})


@pytest.fixture()
def cleanup_users() -> Iterator[list[uuid.UUID]]:
    """Track user IDs created in a test; remove their data in
    FK-safe order on teardown (children → parents)."""
    user_ids: list[uuid.UUID] = []
    yield user_ids
    if not user_ids:
        return
    with SessionLocal() as db:
        for table in (
            "detection_runs",
            "jobs",
            "report_events",
            "report_versions",
        ):
            _delete_children_for_users(db, table, user_ids)
        stmt = text(
            "DELETE FROM reports WHERE user_id IN :ids"
        ).bindparams(bindparam("ids", expanding=True))
        db.execute(stmt, {"ids": user_ids})
        db.execute(delete(User).where(User.id.in_(user_ids)))
        db.commit()


def _register_login(
    cleanup_users: list[uuid.UUID],
) -> tuple[uuid.UUID, str]:
    email = f"api-dt-{uuid.uuid4().hex}@example.com"
    password = "Correct Horse Battery Staple!"
    r = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password},
    )
    assert r.status_code == 201, r.text
    uid = uuid.UUID(r.json()["id"])
    cleanup_users.append(uid)
    r = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert r.status_code == 200, r.text
    return uid, r.json()["access_token"]


def _seed_report_and_version(
    uid: uuid.UUID,
) -> tuple[uuid.UUID, uuid.UUID]:
    with SessionLocal() as db:
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
    return rid, vid


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_enqueue_detection_returns_201(
    cleanup_users: list[uuid.UUID],
) -> None:
    uid, token = _register_login(cleanup_users)
    rid, vid = _seed_report_and_version(uid)
    r = client.post(
        f"/api/v1/reports/{rid}/versions/{vid}/detect",
        headers=_auth(token),
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "queued"
    assert body["report_id"] == str(rid)
    assert body["version_id"] == str(vid)


def test_enqueue_detection_foreign_report_404(
    cleanup_users: list[uuid.UUID],
) -> None:
    _uid_a, token_a = _register_login(cleanup_users)
    uid_b, _token_b = _register_login(cleanup_users)
    rid_b, vid_b = _seed_report_and_version(uid_b)
    r = client.post(
        f"/api/v1/reports/{rid_b}/versions/{vid_b}/detect",
        headers=_auth(token_a),
    )
    assert r.status_code == 404


def test_enqueue_detection_foreign_version_under_own_report_404(
    cleanup_users: list[uuid.UUID],
) -> None:
    uid_a, token_a = _register_login(cleanup_users)
    uid_b, _token_b = _register_login(cleanup_users)
    rid_a, _vid_a = _seed_report_and_version(uid_a)
    _rid_b, vid_b = _seed_report_and_version(uid_b)
    r = client.post(
        f"/api/v1/reports/{rid_a}/versions/{vid_b}/detect",
        headers=_auth(token_a),
    )
    assert r.status_code == 404


def test_get_detection_wrong_version_404(
    cleanup_users: list[uuid.UUID],
) -> None:
    uid, token = _register_login(cleanup_users)
    rid, _vid = _seed_report_and_version(uid)
    other_version = uuid.uuid4()
    r = client.get(
        f"/api/v1/reports/{rid}/versions/{other_version}/detection",
        headers=_auth(token),
    )
    assert r.status_code == 404
