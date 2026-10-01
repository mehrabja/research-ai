import uuid
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.api.dependencies import get_current_user
from app.core.config import get_settings
from app.db.models.experiment_result import ExperimentResult
from app.db.models.metric import Metric
from app.db.models.project import Project, ProjectEvent
from app.db.models.project_file import ProjectFile
from app.db.models.report import Report
from app.db.models.source import Chunk, Source
from app.db.models.technical_fact import TechnicalFact
from app.db.models.technical_intelligence import TechnicalIntelligenceRun
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
        pids = select(Project.id).where(Project.user_id.in_(uids))
        db.execute(
            delete(ProjectEvent).where(
                ProjectEvent.project_id.in_(pids)
            )
        )
        db.execute(delete(Project).where(Project.user_id.in_(uids)))
        # M37: purge owned workspaces before deleting user
        db.execute(
            delete(Workspace).where(
                Workspace.owner_user_id.in_(uids)
            )
        )
        db.execute(delete(User).where(User.id.in_(uids)))
        db.commit()


def _mk_user(uids) -> uuid.UUID:
    uid = uuid.uuid4()
    with SessionLocal() as db:
        db.add(User(
            id=uid,
            email=f"rag-api-{uid.hex[:8]}@e.com",
            password_hash="x",
        ))
        db.commit()
    uids.append(uid)
    return uid


@pytest.fixture()
def client(cleanup_users):
    uid = _mk_user(cleanup_users)

    def _override_user():
        with SessionLocal() as db:
            u = db.get(User, uid)
            assert u is not None
            return u

    def _override_db():
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


def _mk_project(uid):
    with SessionLocal() as db:
        p = projects_service.create_project(
            db, user_id=uid, name="P"
        )
        return p.id


def test_memory_endpoint_empty(client):
    c, uid = client
    pid = _mk_project(uid)
    resp = c.get(f"/api/v1/projects/{pid}/rag/memory")
    assert resp.status_code == 200
    assert resp.json() == {"items": [], "total": 0}


def test_ownership_isolation(client):
    c, uid = client
    other_uid = _mk_user([])
    with SessionLocal() as db:
        other_p = projects_service.create_project(
            db, user_id=other_uid, name="other"
        )
        other_pid = other_p.id
    try:
        resp = c.post(
            f"/api/v1/projects/{other_pid}/rag/retrieve",
            json={"query": "x", "mode": "lexical", "async": False},
        )
        assert resp.status_code == 404
    finally:
        with SessionLocal() as db:
            db.execute(
                delete(ProjectEvent).where(
                    ProjectEvent.project_id == other_pid
                )
            )
            db.execute(delete(Project).where(Project.id == other_pid))
            # M37: purge owned workspaces before deleting user
            db.execute(
                delete(Workspace).where(
                    Workspace.owner_user_id == other_uid
                )
            )
            db.execute(delete(User).where(User.id == other_uid))
            db.commit()


def test_retrieval_result_exposes_canonical_evidence_metadata():
    from types import SimpleNamespace

    from app.api.routes.rag import _result_row_to_read

    chunk_id = uuid.uuid4()
    project_file_id = uuid.uuid4()
    row = SimpleNamespace(
        rank=1,
        chunk_id=chunk_id,
        source_id=uuid.uuid4(),
        final_score=0.9,
        vector_score=None,
        lexical_score=0.8,
        graph_score=None,
        memory_score=None,
        quality_score=None,
        diversity_penalty=None,
        retrieval_stage="candidate",
        retrieval_reason=["lexical_match"],
        graph_distance=None,
        memory_match=None,
        result_meta={
            "evidence_key": f"retrieval_chunk:{chunk_id}",
            "project_file_id": str(project_file_id),
        },
    )

    out = _result_row_to_read(row)

    assert out.evidence_key == f"retrieval_chunk:{chunk_id}"
    assert out.project_file_id == project_file_id


def test_canonical_project_evidence_endpoint_empty(client):
    c, uid = client
    pid = _mk_project(uid)
    resp = c.get(f"/api/v1/projects/{pid}/evidence")
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"items": [], "total": 0, "limit": 100, "offset": 0}

    filtered = c.get(
        f"/api/v1/projects/{pid}/evidence",
        params={"kind": "retrieval_chunk", "limit": 10},
    )
    assert filtered.status_code == 200
    assert filtered.json() == {
        "items": [],
        "total": 0,
        "limit": 10,
        "offset": 0,
    }

    invalid = c.get(
        f"/api/v1/projects/{pid}/evidence",
        params={"kind": "m28_evidence"},
    )
    assert invalid.status_code == 422


def test_canonical_project_evidence_endpoint_returns_file_and_chunk_records(
    client,
):
    c, uid = client
    pid = _mk_project(uid)
    file_id = uuid.uuid4()
    report_id = uuid.uuid4()
    source_id = uuid.uuid4()
    chunk_id = uuid.uuid4()
    run_id = uuid.uuid4()
    fact_id = uuid.uuid4()
    result_id = uuid.uuid4()
    metric_id = uuid.uuid4()

    with SessionLocal() as db:
        db.add(
            ProjectFile(
                id=file_id,
                project_id=pid,
                uploaded_by=uid,
                original_filename="evidence.pdf",
                normalized_filename="evidence.pdf",
                extension="pdf",
                storage_key=f"projects/{pid}/evidence.pdf",
                storage_provider="local",
                size_bytes=123,
                sha256="a" * 64,
                client_mime_type="application/pdf",
                detected_mime_type="application/pdf",
                file_kind="pdf",
                status="ready",
                extraction_status="completed",
                extracted_text="canonical project file text",
                extraction_pipeline_version="pdf-v1",
            )
        )
        db.add(
            Report(
                id=report_id,
                user_id=uid,
                project_id=pid,
                topic="Evidence API contract",
                status="draft",
                output_language="en",
            )
        )
        db.add(
            Source(
                id=source_id,
                report_id=report_id,
                title="evidence.pdf",
                source_api="project_file",
                external_source_id=str(file_id),
                full_text="canonical project file text",
                status="full_text",
            )
        )
        db.flush()
        db.add(
            Chunk(
                id=chunk_id,
                source_id=source_id,
                content="retrieval chunk text",
                chunk_index=0,
                char_start=0,
                char_end=21,
                page_number=1,
                embedding_status="completed",
                chunk_meta={"project_file_id": str(file_id)},
            )
        )
        db.add(
            TechnicalIntelligenceRun(
                id=run_id,
                project_id=pid,
                context_hash="ctx-m29",
                m29_version="m29.1",
                status="completed",
            )
        )
        db.flush()
        db.add(
            TechnicalFact(
                id=fact_id,
                technical_intelligence_run_id=run_id,
                project_id=pid,
                project_file_id=file_id,
                fact_type="configuration",
                fact_key="learning_rate",
                fact_value="0.001",
                normalized_value="0.001",
                confidence=0.9,
                provenance={},
                context_hash="ctx-m29",
                status="extracted",
            )
        )
        db.flush()
        db.add(
            ExperimentResult(
                id=result_id,
                technical_intelligence_run_id=run_id,
                project_id=pid,
                project_file_id=file_id,
                result_type="metric_observation",
                name="validation_accuracy",
                description="Validation accuracy result",
                value={"accuracy": 0.91},
                unit=None,
                experiment_key="exp-1",
                provenance={},
                context_hash="ctx-m29",
                status="parsed",
            )
        )
        db.flush()
        db.add(
            Metric(
                id=metric_id,
                technical_intelligence_run_id=run_id,
                project_id=pid,
                experiment_result_id=result_id,
                name="accuracy",
                normalized_name="accuracy",
                value_numeric=0.91,
                unit=None,
                split="validation",
                direction="higher",
                baseline_value=None,
                delta_value=None,
                is_primary=True,
                provenance={},
                context_hash="ctx-m29",
                status="parsed",
            )
        )
        db.commit()

    try:
        resp = c.get(f"/api/v1/projects/{pid}/evidence")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 5
        assert body["limit"] == 100
        assert body["offset"] == 0

        records = {item["kind"]: item for item in body["items"]}
        assert set(records) == {
            "project_file",
            "retrieval_chunk",
            "m29_technical_fact",
            "m29_experiment_result",
            "m29_metric",
        }
        assert records["project_file"]["evidence_id"] == str(file_id)
        assert records["project_file"]["project_file_id"] == str(file_id)
        assert records["project_file"]["text"] == "canonical project file text"
        assert records["retrieval_chunk"]["evidence_id"] == str(chunk_id)
        assert records["retrieval_chunk"]["chunk_id"] == str(chunk_id)
        assert records["retrieval_chunk"]["project_file_id"] == str(file_id)
        assert records["retrieval_chunk"]["locator"] == {
            "page_number": 1,
            "char_start": 0,
            "char_end": 21,
        }

        assert records["m29_technical_fact"]["project_file_id"] == str(file_id)
        assert records["m29_experiment_result"]["project_file_id"] == str(file_id)
        assert records["m29_metric"]["project_file_id"] == str(file_id)

        filtered = c.get(
            f"/api/v1/projects/{pid}/evidence",
            params={"kind": "m29_metric", "file_id": str(file_id)},
        )
        assert filtered.status_code == 200
        filtered_body = filtered.json()
        assert filtered_body["total"] == 1
        assert len(filtered_body["items"]) == 1
        assert filtered_body["items"][0]["kind"] == "m29_metric"
        assert filtered_body["items"][0]["project_file_id"] == str(file_id)

        with SessionLocal() as db:
            project_file = db.get(ProjectFile, file_id)
            assert project_file is not None
            project_file.status = "deleted"
            project_file.deleted_at = datetime.now(UTC)
            db.commit()

        hidden = c.get(f"/api/v1/projects/{pid}/evidence")
        assert hidden.status_code == 200
        assert hidden.json() == {
            "items": [],
            "total": 0,
            "limit": 100,
            "offset": 0,
        }
    finally:
        with SessionLocal() as db:
            db.execute(delete(Metric).where(Metric.id == metric_id))
            db.execute(delete(ExperimentResult).where(ExperimentResult.id == result_id))
            db.execute(delete(TechnicalFact).where(TechnicalFact.id == fact_id))
            db.execute(delete(TechnicalIntelligenceRun).where(TechnicalIntelligenceRun.id == run_id))
            db.execute(delete(Chunk).where(Chunk.id == chunk_id))
            db.execute(delete(Source).where(Source.id == source_id))
            db.execute(delete(Report).where(Report.id == report_id))
            db.execute(delete(ProjectFile).where(ProjectFile.id == file_id))
            db.commit()
