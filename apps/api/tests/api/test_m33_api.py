"""M33 — API tests."""
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
from app.db.models.project import Project, ProjectEvent
from app.db.models.publication import (
    PublicationComplianceFinding,
    PublicationComplianceRun,
    PublicationTarget,
    PublicationTargetSelection,
)
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
from app.services.publication import profiles as pub_profiles
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
        if rids:
            db.execute(delete(PublicationComplianceFinding).where(
                PublicationComplianceFinding.report_id.in_(rids)
            ))
            db.execute(delete(PublicationComplianceRun).where(
                PublicationComplianceRun.report_id.in_(rids)
            ))
            db.execute(delete(PublicationTargetSelection).where(
                PublicationTargetSelection.report_id.in_(rids)
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
            email=f"m33a-{uid.hex[:8]}@e.com",
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
    return rid, vid


def _mk_target() -> uuid.UUID:
    with SessionLocal() as db:
        t = pub_profiles.create_target_profile(
            db,
            target_code=f"api-{uuid.uuid4().hex[:8]}",
            profile_version="1.0.0",
            venue="Test Journal",
            venue_type="journal",
            citation_style="numeric",
        )
        db.commit()
        return t.id


def test_requires_auth() -> None:
    c = TestClient(app)
    r = c.post(
        f"/api/v1/reports/{uuid.uuid4()}/publication-compliance/generate",
        json={
            "manuscript_version_id": str(uuid.uuid4()),
            "target_id": str(uuid.uuid4()),
            "async": False,
        },
    )
    assert r.status_code in (401, 403)


def test_create_and_get_target(client) -> None:
    c, _ = client
    code = f"t-{uuid.uuid4().hex[:8]}"
    r = c.post(
        "/api/v1/publication-targets",
        json={
            "target_code": code,
            "profile_version": "1.0.0",
            "venue": "Test Journal",
            "venue_type": "journal",
            "citation_style": "numeric",
        },
    )
    assert r.status_code == 200
    body = r.json()
    tid = body["id"]
    r2 = c.get(f"/api/v1/publication-targets/{tid}")
    assert r2.status_code == 200
    assert r2.json()["target_code"] == code


def test_list_targets(client) -> None:
    c, _ = client
    _mk_target()
    r = c.get("/api/v1/publication-targets")
    assert r.status_code == 200
    assert r.json()["total"] >= 1


def test_select_target(client) -> None:
    c, uid = client
    rid, _vid = _setup(uid)
    tid = _mk_target()
    r = c.post(
        f"/api/v1/reports/{rid}/publication-target/select",
        json={"target_id": str(tid)},
    )
    assert r.status_code == 200
    r2 = c.get(f"/api/v1/reports/{rid}/publication-target/current")
    assert r2.status_code == 200
    assert r2.json()["target_id"] == str(tid)


def test_generate_compliance(client) -> None:
    c, uid = client
    rid, vid = _setup(uid)
    tid = _mk_target()
    r = c.post(
        f"/api/v1/reports/{rid}/publication-compliance/generate",
        json={
            "manuscript_version_id": str(vid),
            "target_id": str(tid),
            "async": False,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "completed"
    assert body["run_id"] is not None
    assert body["gate"] in (
        "pass", "pass_with_warnings", "blocked",
    )


def test_current_compliance(client) -> None:
    c, uid = client
    rid, vid = _setup(uid)
    tid = _mk_target()
    c.post(
        f"/api/v1/reports/{rid}/publication-compliance/generate",
        json={
            "manuscript_version_id": str(vid),
            "target_id": str(tid),
            "async": False,
        },
    )
    r = c.get(f"/api/v1/reports/{rid}/publication-compliance/current")
    assert r.status_code == 200
    body = r.json()
    assert body["run"]["status"] == "completed"


def test_idempotent_second_run(client) -> None:
    c, uid = client
    rid, vid = _setup(uid)
    tid = _mk_target()
    payload = {
        "manuscript_version_id": str(vid),
        "target_id": str(tid),
        "async": False,
    }
    r1 = c.post(
        f"/api/v1/reports/{rid}/publication-compliance/generate",
        json=payload,
    )
    assert r1.json()["status"] == "completed"
    r2 = c.post(
        f"/api/v1/reports/{rid}/publication-compliance/generate",
        json=payload,
    )
    assert r2.json()["status"] == "completed"


def test_checklist(client) -> None:
    c, uid = client
    rid, vid = _setup(uid)
    tid = _mk_target()
    c.post(
        f"/api/v1/reports/{rid}/publication-compliance/generate",
        json={
            "manuscript_version_id": str(vid),
            "target_id": str(tid),
            "async": False,
        },
    )
    r = c.get(
        f"/api/v1/reports/{rid}/publication-compliance/checklist"
    )
    assert r.status_code == 200
    body = r.json()
    assert body["target_profile_version"] == "1.0.0"


def test_cross_user_404(cleanup_users) -> None:
    owner = _mk_user(cleanup_users)
    other = _mk_user(cleanup_users)
    rid, _vid = _setup(owner)

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
        r = c.get(
            f"/api/v1/reports/{rid}/publication-compliance/current"
        )
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 404


_ = PublicationTarget
