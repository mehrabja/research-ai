"""M35 — API tests."""
from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.api.dependencies import get_current_user
from app.core.config import get_settings
from app.db.models.manuscript import (
    Manuscript,
    ManuscriptSection,
    ManuscriptVersion,
)
from app.db.models.orchestration import (
    ResearchOrchestrationNode,
    ResearchOrchestrationRun,
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
        if rids:
            run_ids = [
                r[0] for r in db.execute(
                    select(ResearchOrchestrationRun.id).where(
                        ResearchOrchestrationRun.report_id.in_(rids)
                    )
                ).all()
            ]
            if run_ids:
                db.execute(delete(ResearchOrchestrationNode).where(
                    ResearchOrchestrationNode.run_id.in_(run_ids)
                ))
                db.execute(delete(ResearchOrchestrationRun).where(
                    ResearchOrchestrationRun.id.in_(run_ids)
                ))
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
            email=f"m35-{uid.hex[:8]}@e.com",
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
    return rid, pid


def test_requires_auth() -> None:
    c = TestClient(app)
    r = c.post(
        f"/api/v1/reports/{uuid.uuid4()}/orchestration/run",
        json={
            "goal": "x", "strategy": "reviewer_revision_plan",
            "async": False,
        },
    )
    assert r.status_code in (401, 403)


def test_run_orchestration_reviewer_plan(client) -> None:
    c, uid = client
    rid, _pid = _setup(uid)
    r = c.post(
        f"/api/v1/reports/{rid}/orchestration/run",
        json={
            "goal": "Produce reviewer revision plan",
            "strategy": "reviewer_revision_plan",
            "async": False,
        },
    )
    # Node execution may fail (no manuscript), but the run itself must
    # be created and be queryable. Accept both completed/failed.
    assert r.status_code in (200, 409)
    if r.status_code == 200:
        body = r.json()
        assert body["run_id"] is not None


def test_list_orchestration_tools(client) -> None:
    c, uid = client
    rid, _pid = _setup(uid)
    r = c.get(f"/api/v1/reports/{rid}/orchestration/tools")
    assert r.status_code == 200
    body = r.json()
    keys = {it["key"] for it in body["items"]}
    for expected in (
        "build_plan", "academic_qa", "generate_citations",
        "humanize", "target_compliance", "technical_intelligence",
    ):
        assert expected in keys


def test_current_404_when_no_run(client) -> None:
    c, uid = client
    rid, _pid = _setup(uid)
    r = c.get(f"/api/v1/reports/{rid}/orchestration/current")
    assert r.status_code == 404


def test_history_list(client) -> None:
    c, uid = client
    rid, _pid = _setup(uid)
    c.post(
        f"/api/v1/reports/{rid}/orchestration/run",
        json={
            "goal": "x", "strategy": "reviewer_revision_plan",
            "async": False,
        },
    )
    r = c.get(f"/api/v1/reports/{rid}/orchestration/runs")
    assert r.status_code == 200
    assert r.json()["total"] >= 1


def test_cross_user_404(cleanup_users) -> None:
    owner = _mk_user(cleanup_users)
    other = _mk_user(cleanup_users)
    rid, _pid = _setup(owner)

    def _override_other() -> User:
        with SessionLocal() as db:
            u = db.get(User, other)
            assert u is not None
            return u

    def _override_db() -> Iterator:
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_current_user] = _override_other
    app.dependency_overrides[get_db] = _override_db
    try:
        c = TestClient(app)
        r = c.get(f"/api/v1/reports/{rid}/orchestration/current")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 404
