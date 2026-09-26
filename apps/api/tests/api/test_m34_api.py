"""M34 — API tests (multi-user collaboration)."""
from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.api.dependencies import get_current_user
from app.core.config import get_settings
from app.db.models.collaboration import (
    ManuscriptBranch,
    ManuscriptComment,
    ManuscriptReviewTask,
    ProjectCollaborationEvent,
    ProjectMember,
)
from app.db.models.manuscript import (
    Manuscript,
    ManuscriptSection,
    ManuscriptVersion,
)
from app.db.models.project import Project, ProjectEvent
from app.db.models.report import Report, ReportEvent
from app.db.models.research_plan import (
    ResearchEvidenceRequirement,
    ResearchPlan,
    ResearchPlanDependency,
    ResearchPlanRun,
    ResearchPlanSection,
)
from app.db.models.user import User
from app.db.models.workspace import Workspace
from app.db.session import SessionLocal, get_db
from app.main import app
from app.services import projects as projects_service
from app.services.manuscript import builder as builder_svc
from app.services.research_planning import planner as planner_svc


@pytest.fixture(autouse=True)
def _clear_settings() -> Iterator[None]:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture()
def cleanup_users() -> Iterator[list[uuid.UUID]]:
    uids: list[uuid.UUID] = []
    yield uids
    if not uids:
        return
    with SessionLocal() as db:
        pids = [
            r[0] for r in db.execute(
                select(Project.id).where(Project.user_id.in_(uids))
            ).all()
        ]
        rids = [
            r[0] for r in db.execute(
                select(Report.id).where(Report.user_id.in_(uids))
            ).all()
        ]
        plan_ids = [
            r[0] for r in db.execute(
                select(ResearchPlan.id).where(
                    ResearchPlan.project_id.in_(pids)
                )
            ).all()
        ]
        version_ids = [
            r[0] for r in db.execute(
                select(ManuscriptVersion.id).where(
                    ManuscriptVersion.manuscript_id.in_(
                        select(Manuscript.id).where(
                            Manuscript.report_id.in_(rids)
                        )
                    )
                )
            ).all()
        ]
        if version_ids:
            db.execute(delete(ManuscriptComment).where(
                ManuscriptComment.manuscript_version_id.in_(version_ids)
            ))
            db.execute(delete(ManuscriptReviewTask).where(
                ManuscriptReviewTask.manuscript_version_id.in_(
                    version_ids
                )
            ))
        if pids:
            db.execute(delete(ProjectMember).where(
                ProjectMember.project_id.in_(pids)
            ))
            db.execute(delete(ProjectCollaborationEvent).where(
                ProjectCollaborationEvent.project_id.in_(pids)
            ))
        manuscript_ids = [
            r[0] for r in db.execute(
                select(Manuscript.id).where(Manuscript.report_id.in_(rids))
            ).all()
        ]
        if manuscript_ids:
            db.execute(delete(ManuscriptBranch).where(
                ManuscriptBranch.manuscript_id.in_(manuscript_ids)
            ))
        if version_ids:
            db.execute(delete(ManuscriptSection).where(
                ManuscriptSection.manuscript_version_id.in_(version_ids)
            ))
            db.execute(delete(ManuscriptVersion).where(
                ManuscriptVersion.id.in_(version_ids)
            ))
        if rids:
            db.execute(delete(Manuscript).where(
                Manuscript.report_id.in_(rids)
            ))
        if pids:
            db.execute(delete(ResearchPlanRun).where(
                ResearchPlanRun.project_id.in_(pids)
            ))
        if plan_ids:
            db.execute(delete(ResearchPlanDependency).where(
                ResearchPlanDependency.plan_id.in_(plan_ids)
            ))
            db.execute(delete(ResearchEvidenceRequirement).where(
                ResearchEvidenceRequirement.plan_id.in_(plan_ids)
            ))
            db.execute(delete(ResearchPlanSection).where(
                ResearchPlanSection.plan_id.in_(plan_ids)
            ))
            db.execute(delete(ResearchPlan).where(
                ResearchPlan.id.in_(plan_ids)
            ))
        if pids:
            db.execute(delete(ProjectEvent).where(
                ProjectEvent.project_id.in_(pids)
            ))
            db.execute(delete(Project).where(Project.id.in_(pids)))
        if rids:
            db.execute(delete(ReportEvent).where(
                ReportEvent.report_id.in_(rids)
            ))
            db.execute(delete(Report).where(Report.id.in_(rids)))
        # M37: purge owned workspaces before deleting user
        db.execute(
            delete(Workspace).where(
                Workspace.owner_user_id.in_(uids)
            )
        )
        db.execute(delete(User).where(User.id.in_(uids)))
        db.commit()


def _mk_user(uids):
    uid = uuid.uuid4()
    with SessionLocal() as db:
        db.add(User(
            id=uid,
            email=f"m34-{uid.hex[:8]}@e.com",
            password_hash="x",
        ))
        db.commit()
    uids.append(uid)
    return uid


@pytest.fixture()
def client(cleanup_users) -> Iterator[tuple[TestClient, uuid.UUID]]:
    uid = _mk_user(cleanup_users)

    def _override_user() -> User:
        with SessionLocal() as db:
            u = db.get(User, uid)
            assert u is not None
            return u

    def _override_db() -> Iterator:
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_current_user] = _override_user
    app.dependency_overrides[get_db] = _override_db
    try:
        yield TestClient(app), uid
    finally:
        app.dependency_overrides.clear()


def _setup(uid):
    with SessionLocal() as db:
        p = projects_service.create_project(
            db, user_id=uid, name="P", domain="computer_science",
        )
        pid = p.id
    rid = uuid.uuid4()
    with SessionLocal() as db:
        db.add(Report(
            id=rid, user_id=uid, project_id=pid,
            topic="T", output_language="en",
        ))
        db.commit()
    with SessionLocal() as db:
        planner_svc.generate_research_plan(
            db, user_id=uid, project_id=pid,
        )
    with SessionLocal() as db:
        result = builder_svc.generate_manuscript(
            db, user_id=uid, report_id=rid,
        )
        vid = result.version.id
        mid = result.version.manuscript_id
    return rid, pid, mid, vid


def test_requires_auth() -> None:
    c = TestClient(app)
    r = c.get(f"/api/v1/projects/{uuid.uuid4()}/members")
    assert r.status_code in (401, 403)


def test_owner_can_list_members(client) -> None:
    c, uid = client
    _rid, pid, _mid, _vid = _setup(uid)
    r = c.get(f"/api/v1/projects/{pid}/members")
    assert r.status_code == 200
    assert r.json()["total"] == 0


def test_add_and_remove_member(client, cleanup_users) -> None:
    c, uid = client
    _rid, pid, _mid, _vid = _setup(uid)
    other = _mk_user(cleanup_users)
    r = c.post(
        f"/api/v1/projects/{pid}/members",
        json={"user_id": str(other), "role": "reviewer"},
    )
    assert r.status_code == 201
    mid = r.json()["id"]

    r2 = c.get(f"/api/v1/projects/{pid}/members")
    assert r2.json()["total"] == 1

    r3 = c.delete(f"/api/v1/projects/{pid}/members/{mid}")
    assert r3.status_code == 204


def test_non_member_cannot_list_members(
    client, cleanup_users,
) -> None:
    c, uid = client
    _rid, pid, _mid, _vid = _setup(uid)
    outsider = _mk_user(cleanup_users)

    def _override_outsider() -> User:
        with SessionLocal() as db:
            u = db.get(User, outsider)
            assert u is not None
            return u

    def _override_db() -> Iterator:
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_current_user] = _override_outsider
    app.dependency_overrides[get_db] = _override_db
    try:
        c2 = TestClient(app)
        r = c2.get(f"/api/v1/projects/{pid}/members")
    finally:
        app.dependency_overrides.clear()
    # Non-member on a foreign project → 404
    assert r.status_code == 404


def test_version_list_returns_current(client) -> None:
    c, uid = client
    _rid, _pid, mid, vid = _setup(uid)
    r = c.get(
        f"/api/v1/reports/{uuid.uuid4()}"
        f"/manuscripts/{mid}/versions"
    )
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 1
    assert any(it["id"] == str(vid) for it in body["items"])


def test_create_branch(client) -> None:
    c, uid = client
    rid, _pid, mid, vid = _setup(uid)
    r = c.post(
        f"/api/v1/reports/{rid}/manuscript-branches",
        json={
            "manuscript_id": str(mid),
            "name": "main",
            "head_version_id": str(vid),
            "is_default": True,
        },
    )
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "main"
    assert body["is_default"] is True


def test_create_and_list_comments(client) -> None:
    c, uid = client
    rid, _pid, _mid, vid = _setup(uid)
    r = c.post(
        f"/api/v1/reports/{rid}/manuscript-versions/{vid}/comments",
        json={"body": "Needs work on methodology"},
    )
    assert r.status_code == 201
    cid = r.json()["id"]

    r2 = c.get(
        f"/api/v1/reports/{rid}/manuscript-versions/{vid}/comments"
    )
    assert r2.status_code == 200
    assert r2.json()["total"] == 1

    r3 = c.post(
        f"/api/v1/reports/{rid}/comments/{cid}/resolve"
    )
    assert r3.status_code == 200
    assert r3.json()["status"] == "resolved"


def test_create_review_task(client) -> None:
    c, uid = client
    rid, _pid, _mid, vid = _setup(uid)
    r = c.post(
        f"/api/v1/reports/{rid}/manuscript-versions/{vid}/reviews",
        json={
            "manuscript_version_id": str(vid),
            "title": "Check numerical claims",
            "severity": "warning",
        },
    )
    assert r.status_code == 201
    tid = r.json()["id"]

    r2 = c.patch(
        f"/api/v1/reports/{rid}/reviews/{tid}",
        json={"status": "resolved", "resolution": {"ok": True}},
    )
    assert r2.status_code == 200
    assert r2.json()["status"] == "resolved"


def test_events_emitted(client) -> None:
    c, uid = client
    rid, pid, _mid, vid = _setup(uid)
    c.post(
        f"/api/v1/reports/{rid}/manuscript-versions/{vid}/comments",
        json={"body": "x"},
    )
    with SessionLocal() as db:
        rows = list(db.execute(
            select(ProjectCollaborationEvent).where(
                ProjectCollaborationEvent.project_id == pid
            )
        ).scalars().all())
    assert any(e.event_type == "comment_created" for e in rows)
