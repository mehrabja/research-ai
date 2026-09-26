"""M37 — Project quota (projects.max) enforcement tests.

Covers:
  * creating under the cap succeeds
  * creating over the cap raises QuotaExceeded
  * archiving frees a slot
  * concurrent creates respect the cap
"""
from __future__ import annotations

import uuid
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import delete, select

from app.core.exceptions import QuotaExceeded
from app.db.models.project import Project, ProjectEvent
from app.db.models.user import User
from app.db.session import SessionLocal
from app.domain.plan import FEATURE_PROJECTS_MAX
from app.services import entitlements as entitlements_service
from app.services import projects as projects_service
from app.services.workspaces import ensure_default_workspace
from tests._m37_cleanup import purge_test_users


@pytest.fixture()
def cleanup_users() -> Iterator[list[uuid.UUID]]:
    uids: list[uuid.UUID] = []
    yield uids
    if not uids:
        return
    with SessionLocal() as db:
        pids = select(Project.id).where(Project.user_id.in_(uids))
        db.execute(
            delete(ProjectEvent).where(ProjectEvent.project_id.in_(pids))
        )
        db.execute(delete(Project).where(Project.user_id.in_(uids)))
        purge_test_users(db, uids)
        db.commit()


def _mk_user(uids: list[uuid.UUID]) -> uuid.UUID:
    uid = uuid.uuid4()
    with SessionLocal() as db:
        db.add(
            User(
                id=uid,
                email=f"q-{uid.hex[:8]}@e.com",
                password_hash="x",
            )
        )
        db.commit()
    uids.append(uid)
    return uid


def _resolve_limit(user_id: uuid.UUID) -> int:
    """Provision the user's default workspace and read projects.max."""
    with SessionLocal() as db:
        ws = ensure_default_workspace(db, user_id=user_id)
        plan = entitlements_service.resolve_active_plan(
            db, workspace_id=ws.id
        )
        assert plan is not None, "no live plan after provisioning"
        limit = entitlements_service.get_limit(
            db, plan_id=plan.id, feature=FEATURE_PROJECTS_MAX
        )
        assert limit is not None, "free plan must define projects.max"
        db.commit()
        return limit


# --- single-call behavior -------------------------------------------------

def test_single_create_under_limit_succeeds(
    cleanup_users: list[uuid.UUID],
) -> None:
    uid = _mk_user(cleanup_users)
    limit = _resolve_limit(uid)
    assert limit >= 1

    with SessionLocal() as db:
        for i in range(limit):
            p = projects_service.create_project(
                db, user_id=uid, name=f"p{i}"
            )
            assert p.workspace_id is not None


def test_create_over_limit_raises_quota_exceeded(
    cleanup_users: list[uuid.UUID],
) -> None:
    uid = _mk_user(cleanup_users)
    limit = _resolve_limit(uid)

    with SessionLocal() as db:
        for i in range(limit):
            projects_service.create_project(
                db, user_id=uid, name=f"p{i}"
            )

    with SessionLocal() as db, pytest.raises(QuotaExceeded) as exc_info:
        projects_service.create_project(
            db, user_id=uid, name="overflow"
        )

    exc = exc_info.value
    assert exc.feature == FEATURE_PROJECTS_MAX
    assert exc.limit == limit
    assert exc.current == limit


def test_archived_project_frees_a_slot(
    cleanup_users: list[uuid.UUID],
) -> None:
    uid = _mk_user(cleanup_users)
    limit = _resolve_limit(uid)

    with SessionLocal() as db:
        pids: list[uuid.UUID] = []
        for i in range(limit):
            p = projects_service.create_project(
                db, user_id=uid, name=f"p{i}"
            )
            pids.append(p.id)

        projects_service.archive_project(
            db, user_id=uid, project_id=pids[0]
        )

        # Slot freed -> one more create succeeds.
        projects_service.create_project(
            db, user_id=uid, name="replacement"
        )


# --- concurrency ----------------------------------------------------------

def test_concurrent_create_respects_projects_max(
    cleanup_users: list[uuid.UUID],
) -> None:
    uid = _mk_user(cleanup_users)
    limit = _resolve_limit(uid)

    n = limit + 2

    def _attempt(i: int) -> str:
        with SessionLocal() as db:
            try:
                projects_service.create_project(
                    db, user_id=uid, name=f"c{i}"
                )
                return "ok"
            except QuotaExceeded:
                return "quota"
            except Exception as exc:  # noqa: BLE001
                return f"err:{type(exc).__name__}:{exc}"

    with ThreadPoolExecutor(max_workers=n) as pool:
        results = list(pool.map(_attempt, range(n)))

    ok = sum(1 for r in results if r == "ok")
    quota = sum(1 for r in results if r == "quota")

    assert ok == limit, results
    assert quota == n - limit, results
# --- audit emission -------------------------------------------------------

import logging  # noqa: E402


class _AuditCapture(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.events: list[dict] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.events.append(dict(record.__dict__))


def test_quota_denied_emits_audit_event(
    cleanup_users: list[uuid.UUID],
) -> None:
    uid = _mk_user(cleanup_users)
    limit = _resolve_limit(uid)

    with SessionLocal() as db:
        for i in range(limit):
            projects_service.create_project(
                db, user_id=uid, name=f"p{i}"
            )

    logger = logging.getLogger("audit")
    handler = _AuditCapture()
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    try:
        with SessionLocal() as db, pytest.raises(QuotaExceeded):
            projects_service.create_project(
                db, user_id=uid, name="overflow"
            )
    finally:
        logger.removeHandler(handler)

    codes = [e.get("event") for e in handler.events]
    assert "QUOTA_DENIED" in codes

    # Payload carries workspace + feature context now.
    denied = next(
        e for e in handler.events if e.get("event") == "QUOTA_DENIED"
    )
    assert denied.get("user_id") == str(uid)
    assert denied.get("workspace_id")
    assert denied.get("feature") == FEATURE_PROJECTS_MAX
    assert denied.get("limit") == limit
    assert denied.get("current") == limit
