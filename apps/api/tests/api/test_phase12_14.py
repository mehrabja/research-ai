"""Unified legacy Phase 12-14 persistence/evidence API tests."""
from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.core.config import get_settings
from app.db.models.jobs import Job
from app.db.models.pdf_workspace import PdfAnnotation, PdfWorkspaceState
from app.db.models.project import Project, ProjectEvent
from app.db.models.project_file import ProjectFile, ProjectFileEvent
from app.db.models.report import Report
from app.db.models.research_canvas import ResearchCanvas
from app.db.models.source import Source
from app.db.models.user import User
from app.db.models.workspace import Workspace
from app.db.session import SessionLocal
from app.main import app
from app.services.rate_limit import set_login_rate_limiter

client = TestClient(app)


@pytest.fixture(autouse=True)
def _env(tmp_path, monkeypatch) -> Iterator[None]:
    monkeypatch.setenv("FILE_STORAGE_LOCAL_ROOT", str(tmp_path))
    get_settings.cache_clear()
    set_login_rate_limiter(None)
    yield
    set_login_rate_limiter(None)
    get_settings.cache_clear()


@pytest.fixture()
def cleanup_users() -> Iterator[list[uuid.UUID]]:
    user_ids: list[uuid.UUID] = []
    yield user_ids
    if not user_ids:
        return

    with SessionLocal() as db:
        project_ids = list(
            db.scalars(
                select(Project.id).where(Project.user_id.in_(user_ids))
            )
        )
        file_ids = list(
            db.scalars(
                select(ProjectFile.id).where(
                    ProjectFile.project_id.in_(project_ids)
                )
            )
        )
        report_ids = list(
            db.scalars(
                select(Report.id).where(Report.user_id.in_(user_ids))
            )
        )

        if file_ids:
            file_external_ids = [str(file_id) for file_id in file_ids]
            source_ids = list(
                db.scalars(
                    select(Source.id).where(
                        Source.external_source_id.in_(file_external_ids)
                    )
                )
            )
            if source_ids:
                db.execute(
                    delete(Source).where(Source.id.in_(source_ids))
                )
            db.execute(
                delete(ProjectFileEvent).where(
                    ProjectFileEvent.project_file_id.in_(file_ids)
                )
            )
            db.execute(
                delete(Job).where(Job.project_file_id.in_(file_ids))
            )
            db.execute(
                delete(ProjectFile).where(ProjectFile.id.in_(file_ids))
            )

        if project_ids:
            db.execute(
                delete(PdfAnnotation).where(
                    PdfAnnotation.project_id.in_(project_ids)
                )
            )
            db.execute(
                delete(PdfWorkspaceState).where(
                    PdfWorkspaceState.project_id.in_(project_ids)
                )
            )
            db.execute(
                delete(ResearchCanvas).where(
                    ResearchCanvas.project_id.in_(project_ids)
                )
            )
            db.execute(
                delete(ProjectEvent).where(
                    ProjectEvent.project_id.in_(project_ids)
                )
            )

        if report_ids:
            db.execute(delete(Report).where(Report.id.in_(report_ids)))

        if project_ids:
            db.execute(delete(Project).where(Project.id.in_(project_ids)))

        db.execute(
            delete(Workspace).where(
                Workspace.owner_user_id.in_(user_ids)
            )
        )
        db.execute(delete(User).where(User.id.in_(user_ids)))
        db.commit()


def _auth_session(
    cleanup_users: list[uuid.UUID],
) -> tuple[uuid.UUID, str]:
    email = f"p12-14-{uuid.uuid4().hex}@example.com"
    password = "Correct Horse Battery Staple!"

    register = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password},
    )
    assert register.status_code == 201, register.text

    user_id = uuid.UUID(register.json()["id"])
    cleanup_users.append(user_id)

    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login.status_code == 200, login.text

    return user_id, login.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_project(token: str, name: str) -> str:
    response = client.post(
        "/api/v1/projects",
        headers=_auth(token),
        json={"name": name},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_pdf_workspace_persistence_and_isolation(cleanup_users):
    _, token = _auth_session(cleanup_users)
    project_id = _create_project(token, "PDF Persistence")

    upload = client.post(
        f"/api/v1/projects/{project_id}/files",
        headers=_auth(token),
        files={"file": ("paper.pdf", b"%PDF-1.4 minimal", "application/pdf")},
    )
    assert upload.status_code == 201, upload.text
    file_id = upload.json()["id"]

    first = client.get(
        f"/api/v1/projects/{project_id}/pdf-workspace",
        headers=_auth(token),
    )
    assert first.status_code == 200, first.text
    assert first.json()["documents"][0]["id"] == file_id

    saved = client.put(
        f"/api/v1/projects/{project_id}/pdf-workspace",
        headers=_auth(token),
        json={
            "active_file_id": file_id,
            "page_number": 7,
            "zoom": 1.5,
            "scroll_x": 12,
            "scroll_y": 48,
        },
    )
    assert saved.status_code == 200, saved.text

    annotation = client.post(
        f"/api/v1/projects/{project_id}/pdf-workspace/annotations",
        headers=_auth(token),
        json={
            "file_id": file_id,
            "kind": "note",
            "page_number": 7,
            "note": "Retain this result.",
        },
    )
    assert annotation.status_code == 201, annotation.text

    loaded = client.get(
        f"/api/v1/projects/{project_id}/pdf-workspace",
        headers=_auth(token),
    )
    assert loaded.status_code == 200
    body = loaded.json()
    assert body["active_file_id"] == file_id
    assert body["page_number"] == 7
    assert body["zoom"] == 1.5
    assert body["scroll_x"] == 12
    assert body["scroll_y"] == 48
    assert body["annotations"][0]["note"] == "Retain this result."

    _, other_token = _auth_session(cleanup_users)
    foreign = client.get(
        f"/api/v1/projects/{project_id}/pdf-workspace",
        headers=_auth(other_token),
    )
    assert foreign.status_code == 404


def test_research_canvas_revision_persistence_and_conflict(cleanup_users):
    _, token = _auth_session(cleanup_users)
    project_id = _create_project(token, "Canvas Persistence")

    initial = client.get(
        f"/api/v1/projects/{project_id}/research-canvas",
        headers=_auth(token),
    )
    assert initial.status_code == 200
    assert initial.json()["revision"] == 1

    payload = {
        "nodes": [
            {
                "id": "idea-1",
                "type": "idea",
                "title": "Hypothesis",
                "body": "Sparse coding improves robustness.",
                "x": 10,
                "y": 20,
            },
        ],
        "edges": [],
        "viewport": {"x": 4, "y": 8, "zoom": 1.25},
        "expected_revision": 1,
    }
    saved = client.put(
        f"/api/v1/projects/{project_id}/research-canvas",
        headers=_auth(token),
        json=payload,
    )
    assert saved.status_code == 200
    assert saved.json()["revision"] == 2

    stale = {**payload, "expected_revision": 1}
    conflict = client.put(
        f"/api/v1/projects/{project_id}/research-canvas",
        headers=_auth(token),
        json=stale,
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "CANVAS_REVISION_CONFLICT"

    loaded = client.get(
        f"/api/v1/projects/{project_id}/research-canvas",
        headers=_auth(token),
    )
    assert loaded.status_code == 200
    assert loaded.json()["nodes"][0]["title"] == "Hypothesis"
    assert loaded.json()["viewport"]["zoom"] == 1.25


def test_project_file_evidence_uses_canonical_source_chunk_bridge(
    cleanup_users,
):
    user_id, token = _auth_session(cleanup_users)
    project_id = _create_project(token, "Evidence Unification")

    upload = client.post(
        f"/api/v1/projects/{project_id}/files",
        headers=_auth(token),
        files={
            "file": (
                "evidence.txt",
                b"Canonical evidence text for the project file bridge.",
                "text/plain",
            )
        },
    )
    assert upload.status_code == 201, upload.text
    file_id = uuid.UUID(upload.json()["id"])

    with SessionLocal() as db:
        project_file = db.get(ProjectFile, file_id)
        assert project_file is not None
        project_file.status = "ready"
        project_file.extraction_status = "completed"
        project_file.extracted_text = (
            "Canonical evidence text for the project file bridge."
        )
        project_file.extraction_pipeline_version = "test-pipeline"
        db.commit()

    report = client.post(
        "/api/v1/reports",
        headers=_auth(token),
        json={
            "topic": "Evidence bridge report",
            "output_language": "en",
            "project_id": project_id,
        },
    )
    assert report.status_code == 201, report.text

    evidence = client.get(
        f"/api/v1/projects/{project_id}/evidence/files",
        headers=_auth(token),
    )
    assert evidence.status_code == 200, evidence.text

    item = next(
        row
        for row in evidence.json()["items"]
        if row["file_id"] == str(file_id)
    )
    assert item["evidence_status"] == "synced"
    assert item["source_count"] == 1
    assert item["chunk_count"] >= 1
    assert str(report.json()["id"]) in item["report_ids"]
