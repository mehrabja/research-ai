"""M27 — API tests."""
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
    ManuscriptRun,
    ManuscriptSection,
    ManuscriptSectionDependency,
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
        pids = select(Project.id).where(Project.user_id.in_(uids))
        rids = select(Report.id).where(Report.user_id.in_(uids))
        plan_ids = select(ResearchPlan.id).where(
            ResearchPlan.project_id.in_(pids)
        )
        version_ids = select(ManuscriptVersion.id).where(
            ManuscriptVersion.manuscript_id.in_(
                select(Manuscript.id).where(Manuscript.report_id.in_(rids))
            )
        )
        section_ids = select(ManuscriptSection.id).where(
            ManuscriptSection.manuscript_version_id.in_(version_ids)
        )

        db.execute(delete(ManuscriptSectionDependency).where(
            ManuscriptSectionDependency.manuscript_version_id.in_(version_ids)
        ))
        db.execute(delete(ManuscriptSection).where(
            ManuscriptSection.id.in_(section_ids)
        ))
        db.execute(delete(ManuscriptVersion).where(
            ManuscriptVersion.id.in_(version_ids)
        ))
        db.execute(delete(Manuscript).where(Manuscript.report_id.in_(rids)))
        db.execute(delete(ManuscriptRun).where(
            ManuscriptRun.report_id.in_(rids)
        ))

        db.execute(delete(ResearchPlanRun).where(
            ResearchPlanRun.project_id.in_(pids)
        ))
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
            ResearchPlan.project_id.in_(pids)
        ))

        db.execute(delete(ReportEvent).where(ReportEvent.report_id.in_(rids)))
        db.execute(delete(Report).where(Report.user_id.in_(uids)))

        db.execute(delete(ProjectEvent).where(
            ProjectEvent.project_id.in_(pids)
        ))
        db.execute(delete(Project).where(Project.user_id.in_(uids)))
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
            id=uid, email=f"msapi-{uid.hex[:8]}@e.com", password_hash="x",
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
            db, user_id=uid, name="P", domain="computer_science"
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
            db, user_id=uid, project_id=pid
        )
    return pid, rid


def test_generate_sync(client):
    c, uid = client
    pid, rid = _setup(uid)
    resp = c.post(
        f"/api/v1/reports/{rid}/manuscript/generate",
        json={"async": False},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] in ("completed", "skipped")
    assert body["manuscript_id"] is not None
    assert (body["section_count"] or 0) >= 4


def test_get_current(client):
    c, uid = client
    pid, rid = _setup(uid)
    c.post(
        f"/api/v1/reports/{rid}/manuscript/generate",
        json={"async": False},
    )
    resp = c.get(f"/api/v1/reports/{rid}/manuscript")
    assert resp.status_code == 200
    body = resp.json()
    assert body["manuscript"]["status"] == "ready"
    assert len(body["sections"]) >= 4


def test_get_section(client):
    c, uid = client
    pid, rid = _setup(uid)
    c.post(
        f"/api/v1/reports/{rid}/manuscript/generate",
        json={"async": False},
    )
    resp = c.get(
        f"/api/v1/reports/{rid}/manuscript/sections/introduction"
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["section_key"] == "introduction"
    assert (
        body["research_contract"]["intent_mapping_version"]
        == "m27-intent-v1"
    )


def test_list_versions(client):
    c, uid = client
    pid, rid = _setup(uid)
    c.post(
        f"/api/v1/reports/{rid}/manuscript/generate",
        json={"async": False},
    )
    resp = c.get(f"/api/v1/reports/{rid}/manuscript/versions")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 1


def test_validate_endpoint(client):
    c, uid = client
    pid, rid = _setup(uid)
    c.post(
        f"/api/v1/reports/{rid}/manuscript/generate",
        json={"async": False},
    )
    resp = c.post(f"/api/v1/reports/{rid}/manuscript/validate")
    assert resp.status_code == 200
    body = resp.json()
    assert body["validation_status"] in ("valid", "invalid")


def test_cross_user_isolation(client):
    c, uid = client
    pid, rid = _setup(uid)
    c.post(
        f"/api/v1/reports/{rid}/manuscript/generate",
        json={"async": False},
    )
    other = uuid.uuid4()
    with SessionLocal() as db:
        db.add(User(
            id=other, email=f"x-{other.hex[:8]}@e.com",
            password_hash="x",
        ))
        db.commit()

    def _override_other() -> User:
        with SessionLocal() as db:
            u = db.get(User, other)
            assert u is not None
            return u

    app.dependency_overrides[get_current_user] = _override_other
    try:
        resp = c.get(f"/api/v1/reports/{rid}/manuscript")
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_db, None)

    # `other` has no Report/Project, so direct delete is safe.
    with SessionLocal() as db:
        # M37: purge owned workspaces before deleting user
        db.execute(
            delete(Workspace).where(
                Workspace.owner_user_id == other
            )
        )
        db.execute(delete(User).where(User.id == other))
        db.commit()

    assert resp.status_code == 404


def test_manuscript_draft_autosave_conflict_and_commit(client):
    c, uid = client
    _pid, rid = _setup(uid)

    generated = c.post(
        f"/api/v1/reports/{rid}/manuscript/generate",
        json={"async": False},
    )
    assert generated.status_code == 200

    current = c.get(f"/api/v1/reports/{rid}/manuscript")
    assert current.status_code == 200
    base = current.json()
    base_version_id = base["version"]["id"]
    sections = [
        {
            "section_key": section["section_key"],
            "title": section["title"] + " edited",
            "purpose": section["purpose"],
            "display_order": section["display_order"],
            "word_budget": section["word_budget"],
        }
        for section in base["sections"]
    ]
    content = {
        "title": base["version"]["title"] + " edited",
        "word_target": base["version"]["word_target"],
        "abstract_direction": base["version"]["abstract_direction"],
        "sections": sections,
    }

    created = c.put(
        f"/api/v1/reports/{rid}/manuscript/draft",
        json={
            "base_version_id": base_version_id,
            "revision": 0,
            "content": content,
        },
    )
    assert created.status_code == 200
    assert created.json()["revision"] == 0

    updated = c.put(
        f"/api/v1/reports/{rid}/manuscript/draft",
        json={
            "base_version_id": base_version_id,
            "revision": 0,
            "content": content,
        },
    )
    assert updated.status_code == 200
    assert updated.json()["revision"] == 1

    stale = c.put(
        f"/api/v1/reports/{rid}/manuscript/draft",
        json={
            "base_version_id": base_version_id,
            "revision": 0,
            "content": content,
        },
    )
    assert stale.status_code == 409

    committed = c.post(
        f"/api/v1/reports/{rid}/manuscript/draft/commit",
        json={
            "base_version_id": base_version_id,
            "revision": 1,
        },
    )
    assert committed.status_code == 201
    new_version = committed.json()
    assert new_version["version"] == base["version"]["version"] + 1
    assert new_version["title"].endswith("edited")

    latest = c.get(f"/api/v1/reports/{rid}/manuscript")
    assert latest.status_code == 200
    latest_body = latest.json()
    assert latest_body["version"]["id"] == new_version["id"]
    assert len(latest_body["sections"]) == len(base["sections"])
    assert latest_body["sections"][0]["title"].endswith("edited")

    draft_after_commit = c.get(
        f"/api/v1/reports/{rid}/manuscript/draft"
    )
    assert draft_after_commit.status_code == 404
