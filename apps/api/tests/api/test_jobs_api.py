"""Job API tests."""
from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select, text

from app.db.models.jobs import Job
from app.db.models.report import Report
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


@pytest.fixture(autouse=True)
def _isolate_jobs() -> Iterator[None]:
    with SessionLocal() as db:
        db.execute(delete(Job))
        db.commit()
    yield
    with SessionLocal() as db:
        db.execute(delete(Job))
        db.commit()


@pytest.fixture()
def cleanup_users() -> Iterator[list[uuid.UUID]]:
    user_ids: list[uuid.UUID] = []
    yield user_ids
    if not user_ids:
        return
    with SessionLocal() as db:
        report_ids_subq = select(Report.id).where(
            Report.user_id.in_(user_ids)
        )
        db.execute(delete(Job).where(Job.user_id.in_(user_ids)))
        db.execute(delete(Report).where(Report.id.in_(report_ids_subq)))
        # M37: purge owned workspaces before deleting user
        db.execute(
            delete(Workspace).where(
                Workspace.owner_user_id.in_(user_ids)
            )
        )
        db.execute(delete(User).where(User.id.in_(user_ids)))
        db.commit()


def _register_and_login(
    cleanup_users: list[uuid.UUID],
) -> tuple[uuid.UUID, str]:
    email = f"jobs-{uuid.uuid4().hex}@example.com"
    password = "Correct Horse Battery Staple!"
    r = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password},
    )
    assert r.status_code == 201, r.text
    user_id = uuid.UUID(r.json()["id"])
    cleanup_users.append(user_id)
    r = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert r.status_code == 200, r.text
    return user_id, r.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_report(token: str) -> str:
    r = client.post(
        "/api/v1/reports",
        headers=_auth(token),
        json={"topic": "T", "output_language": "en"},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_enqueue_requires_auth() -> None:
    assert client.post(
        "/api/v1/jobs", json={"job_type": "test_noop"}
    ).status_code == 401


def test_list_requires_auth() -> None:
    assert client.get("/api/v1/jobs").status_code == 401


def test_enqueue_test_noop_succeeds(
    cleanup_users: list[uuid.UUID],
) -> None:
    _, token = _register_and_login(cleanup_users)
    r = client.post(
        "/api/v1/jobs",
        headers=_auth(token),
        json={"job_type": "test_noop", "payload": {"mode": "success"}},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["job_type"] == "test_noop"
    assert body["status"] == "queued"


def test_enqueue_unknown_job_type_400(
    cleanup_users: list[uuid.UUID],
) -> None:
    _, token = _register_and_login(cleanup_users)
    r = client.post(
        "/api/v1/jobs",
        headers=_auth(token),
        json={"job_type": "does_not_exist"},
    )
    assert r.status_code == 400


def test_enqueue_idempotent(
    cleanup_users: list[uuid.UUID],
) -> None:
    _, token = _register_and_login(cleanup_users)
    body = {
        "job_type": "test_noop",
        "payload": {},
        "idempotency_key": "same-key-xyz",
    }
    r1 = client.post("/api/v1/jobs", headers=_auth(token), json=body)
    r2 = client.post("/api/v1/jobs", headers=_auth(token), json=body)
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["id"] == r2.json()["id"]


def test_get_job(
    cleanup_users: list[uuid.UUID],
) -> None:
    _, token = _register_and_login(cleanup_users)
    r = client.post(
        "/api/v1/jobs",
        headers=_auth(token),
        json={"job_type": "test_noop"},
    )
    jid = r.json()["id"]
    r = client.get(f"/api/v1/jobs/{jid}", headers=_auth(token))
    assert r.status_code == 200
    assert r.json()["id"] == jid


def test_get_foreign_job_404(
    cleanup_users: list[uuid.UUID],
) -> None:
    _, token_a = _register_and_login(cleanup_users)
    _, token_b = _register_and_login(cleanup_users)
    r = client.post(
        "/api/v1/jobs",
        headers=_auth(token_a),
        json={"job_type": "test_noop"},
    )
    jid = r.json()["id"]
    assert client.get(
        f"/api/v1/jobs/{jid}", headers=_auth(token_b)
    ).status_code == 404


def test_list_jobs_only_own(
    cleanup_users: list[uuid.UUID],
) -> None:
    _, token_a = _register_and_login(cleanup_users)
    _, token_b = _register_and_login(cleanup_users)
    for _ in range(2):
        client.post(
            "/api/v1/jobs",
            headers=_auth(token_a),
            json={"job_type": "test_noop"},
        )
    client.post(
        "/api/v1/jobs",
        headers=_auth(token_b),
        json={"job_type": "test_noop"},
    )
    a_items = client.get(
        "/api/v1/jobs", headers=_auth(token_a)
    ).json()
    b_items = client.get(
        "/api/v1/jobs", headers=_auth(token_b)
    ).json()
    assert len(a_items) == 2
    assert len(b_items) == 1


def test_cancel_queued_job(
    cleanup_users: list[uuid.UUID],
) -> None:
    _, token = _register_and_login(cleanup_users)
    r = client.post(
        "/api/v1/jobs",
        headers=_auth(token),
        json={"job_type": "test_noop"},
    )
    jid = r.json()["id"]
    r = client.post(
        f"/api/v1/jobs/{jid}/cancel", headers=_auth(token)
    )
    assert r.status_code == 200
    assert r.json()["job"]["status"] == "cancelled"


def test_cancel_foreign_job_404(
    cleanup_users: list[uuid.UUID],
) -> None:
    _, token_a = _register_and_login(cleanup_users)
    _, token_b = _register_and_login(cleanup_users)
    r = client.post(
        "/api/v1/jobs",
        headers=_auth(token_a),
        json={"job_type": "test_noop"},
    )
    jid = r.json()["id"]
    assert client.post(
        f"/api/v1/jobs/{jid}/cancel", headers=_auth(token_b)
    ).status_code == 404


def test_enqueue_embedding_source_missing_payload_422(
    cleanup_users: list[uuid.UUID],
) -> None:
    _, token = _register_and_login(cleanup_users)
    r = client.post(
        "/api/v1/jobs",
        headers=_auth(token),
        json={"job_type": "embedding_source", "payload": {}},
    )
    assert r.status_code == 422


def test_enqueue_embedding_source_valid(
    cleanup_users: list[uuid.UUID],
) -> None:
    user_id, token = _register_and_login(cleanup_users)
    report_id = _create_report(token)
    with SessionLocal() as db:
        sid = db.execute(
            text(
                "INSERT INTO sources (report_id, title, status) "
                "VALUES (:r, 'T', 'full_text') RETURNING id"
            ),
            {"r": report_id},
        ).scalar()
        db.commit()
    r = client.post(
        "/api/v1/jobs",
        headers=_auth(token),
        json={
            "job_type": "embedding_source",
            "payload": {
                "report_id": report_id,
                "source_id": str(sid),
            },
        },
    )
    assert r.status_code == 201, r.text
    assert r.json()["job_type"] == "embedding_source"
    _ = user_id


def test_enqueue_generate_report_missing_payload_422(
    cleanup_users: list[uuid.UUID],
) -> None:
    _, token = _register_and_login(cleanup_users)
    r = client.post(
        "/api/v1/jobs",
        headers=_auth(token),
        json={"job_type": "generate_report", "payload": {}},
    )
    assert r.status_code == 422


def test_enqueue_generate_report_valid(
    cleanup_users: list[uuid.UUID],
) -> None:
    _, token = _register_and_login(cleanup_users)
    report_id = _create_report(token)
    r = client.post(
        "/api/v1/jobs",
        headers=_auth(token),
        json={
            "job_type": "generate_report",
            "payload": {"report_id": report_id},
        },
    )
    assert r.status_code == 201, r.text
    assert r.json()["job_type"] == "generate_report"


def test_enqueue_generate_report_foreign_report_404(
    cleanup_users: list[uuid.UUID],
) -> None:
    _, token_a = _register_and_login(cleanup_users)
    _, token_b = _register_and_login(cleanup_users)
    report_b = _create_report(token_b)
    r = client.post(
        "/api/v1/jobs",
        headers=_auth(token_a),
        json={
            "job_type": "generate_report",
            "payload": {"report_id": report_b},
        },
    )
    assert r.status_code == 404


def test_manual_retry_cancelled_job_requeues_and_is_idempotent(
    cleanup_users: list[uuid.UUID],
) -> None:
    _, token = _register_and_login(cleanup_users)
    r = client.post(
        "/api/v1/jobs",
        headers=_auth(token),
        json={
            "job_type": "test_noop",
            "payload": {"mode": "success"},
            "idempotency_key": "retry-api-" + str(uuid.uuid4()),
            "max_attempts": 3,
        },
    )
    assert r.status_code == 201, r.text
    job_id = r.json()["id"]

    cancelled = client.post(
        f"/api/v1/jobs/{job_id}/cancel",
        headers=_auth(token),
    )
    assert cancelled.status_code == 200, cancelled.text

    retried = client.post(
        f"/api/v1/jobs/{job_id}/retry",
        headers=_auth(token),
    )
    assert retried.status_code == 200, retried.text
    assert retried.json()["id"] == job_id
    assert retried.json()["status"] == "queued"
    assert retried.json()["attempt_count"] == 0

    repeated = client.post(
        f"/api/v1/jobs/{job_id}/retry",
        headers=_auth(token),
    )
    assert repeated.status_code == 200, repeated.text
    assert repeated.json()["id"] == job_id
    assert repeated.json()["status"] == "queued"
    assert repeated.json()["attempt_count"] == 0


def test_manual_retry_foreign_job_is_hidden(
    cleanup_users: list[uuid.UUID],
) -> None:
    _, token_a = _register_and_login(cleanup_users)
    _, token_b = _register_and_login(cleanup_users)

    r = client.post(
        "/api/v1/jobs",
        headers=_auth(token_a),
        json={"job_type": "test_noop"},
    )
    assert r.status_code == 201, r.text
    job_id = r.json()["id"]

    client.post(
        f"/api/v1/jobs/{job_id}/cancel",
        headers=_auth(token_a),
    )

    retry = client.post(
        f"/api/v1/jobs/{job_id}/retry",
        headers=_auth(token_b),
    )
    assert retry.status_code == 404


def test_manual_retry_completed_job_is_rejected(
    cleanup_users: list[uuid.UUID],
) -> None:
    _, token = _register_and_login(cleanup_users)
    r = client.post(
        "/api/v1/jobs",
        headers=_auth(token),
        json={"job_type": "test_noop"},
    )
    assert r.status_code == 201, r.text
    job_id = r.json()["id"]

    from app.services.jobs import claim_job, complete_job

    with SessionLocal() as db:
        claimed = claim_job(db, worker_id="f10-test-worker")
        assert claimed is not None
        assert claimed.id == uuid.UUID(job_id)
        complete_job(
            db,
            job_id=claimed.id,
            worker_id="f10-test-worker",
        )

    retry = client.post(
        f"/api/v1/jobs/{job_id}/retry",
        headers=_auth(token),
    )
    assert retry.status_code == 400
