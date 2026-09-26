"""M23 — Literature clustering tests.

Clustering uses per-source mean embeddings. Tests seed Chunks with
deterministic vectors so that similarity is predictable.
"""
from __future__ import annotations

import math
import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import delete, select

from app.core.config import get_settings
from app.db.models.literature import (
    LiteratureCluster,
    LiteratureClusterMember,
    ProjectLiteratureItem,
)
from app.db.models.project import Project, ProjectEvent
from app.db.models.report import Report
from app.db.models.source import Chunk, Source
from app.db.models.user import User
from app.db.models.workspace import Workspace
from app.db.session import SessionLocal
from app.services import projects as projects_service
from app.services.literature import clustering

EMB_DIM = 1536


def _vec(seed: int, *, base: float = 0.0) -> list[float]:
    """Deterministic embedding. Same seed → nearly identical vector."""
    v = [0.0] * EMB_DIM
    for i in range(8):
        v[i] = math.sin(seed + i) + base
    return v


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
            delete(LiteratureClusterMember).where(
                LiteratureClusterMember.cluster_id.in_(
                    select(LiteratureCluster.id).where(
                        LiteratureCluster.project_id.in_(pids)
                    )
                )
            )
        )
        db.execute(
            delete(LiteratureCluster).where(
                LiteratureCluster.project_id.in_(pids)
            )
        )
        db.execute(
            delete(ProjectLiteratureItem).where(
                ProjectLiteratureItem.project_id.in_(pids)
            )
        )
        rids = select(Report.id).where(Report.project_id.in_(pids))
        db.execute(
            delete(Chunk).where(
                Chunk.source_id.in_(
                    select(Source.id).where(Source.report_id.in_(rids))
                )
            )
        )
        db.execute(delete(Source).where(Source.report_id.in_(rids)))
        db.execute(delete(Report).where(Report.project_id.in_(pids)))
        db.execute(
            delete(ProjectEvent).where(ProjectEvent.project_id.in_(pids))
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
        db.add(
            User(
                id=uid,
                email=f"lit-cl-{uid.hex[:8]}@e.com",
                password_hash="x",
            )
        )
        db.commit()
    uids.append(uid)
    return uid


def _add_source(
    db, report_id, *, title: str, vector: list[float]
) -> uuid.UUID:
    s = Source(report_id=report_id, title=title, status="full_text")
    db.add(s)
    db.flush()
    c = Chunk(
        source_id=s.id,
        content="x",
        chunk_index=0,
        embedding=vector,
        embedding_status="completed",
    )
    db.add(c)
    db.flush()
    return s.id


def test_similar_sources_cluster(cleanup_users):
    uid = _mk_user(cleanup_users)
    with SessionLocal() as db:
        p = projects_service.create_project(db, user_id=uid, name="P")
        r = Report(
            user_id=uid,
            project_id=p.id,
            topic="R",
            output_language="en",
            status="draft",
        )
        db.add(r)
        db.flush()
        v1 = _vec(1)
        v2 = _vec(1, base=0.0001)  # nearly identical
        s1 = _add_source(db, r.id, title="A", vector=v1)
        s2 = _add_source(db, r.id, title="B", vector=v2)
        db.add_all(
            [
                ProjectLiteratureItem(
                    project_id=p.id,
                    source_id=s1,
                    screening_status="candidate",
                    relevance_score=0.8,
                ),
                ProjectLiteratureItem(
                    project_id=p.id,
                    source_id=s2,
                    screening_status="candidate",
                    relevance_score=0.7,
                ),
            ]
        )
        db.commit()
        pid = p.id

    with SessionLocal() as db:
        clusters = clustering.cluster_project_literature(
            db, project_id=pid
        )
        db.commit()
    assert len(clusters) == 1
    assert clusters[0].source_count == 2


def test_unrelated_sources_separate(cleanup_users):
    uid = _mk_user(cleanup_users)
    with SessionLocal() as db:
        p = projects_service.create_project(db, user_id=uid, name="P")
        r = Report(
            user_id=uid,
            project_id=p.id,
            topic="R",
            output_language="en",
            status="draft",
        )
        db.add(r)
        db.flush()
        s1 = _add_source(db, r.id, title="A", vector=_vec(1))
        s2 = _add_source(db, r.id, title="B", vector=_vec(999))
        db.add_all(
            [
                ProjectLiteratureItem(
                    project_id=p.id,
                    source_id=s1,
                    screening_status="candidate",
                ),
                ProjectLiteratureItem(
                    project_id=p.id,
                    source_id=s2,
                    screening_status="candidate",
                ),
            ]
        )
        db.commit()
        pid = p.id

    with SessionLocal() as db:
        clusters = clustering.cluster_project_literature(
            db, project_id=pid
        )
        db.commit()
    assert len(clusters) == 0


def test_clustering_deterministic(cleanup_users):
    uid = _mk_user(cleanup_users)
    with SessionLocal() as db:
        p = projects_service.create_project(db, user_id=uid, name="P")
        r = Report(
            user_id=uid,
            project_id=p.id,
            topic="R",
            output_language="en",
            status="draft",
        )
        db.add(r)
        db.flush()
        ids = [
            _add_source(db, r.id, title=f"S{i}", vector=_vec(i))
            for i in range(3)
        ]
        db.add_all(
            [
                ProjectLiteratureItem(
                    project_id=p.id,
                    source_id=sid,
                    screening_status="candidate",
                )
                for sid in ids
            ]
        )
        db.commit()
        pid = p.id

    with SessionLocal() as db:
        c1 = clustering.cluster_project_literature(
            db, project_id=pid
        )
        n1 = len(c1)
        db.commit()
    with SessionLocal() as db:
        c2 = clustering.cluster_project_literature(
            db, project_id=pid
        )
        n2 = len(c2)
        db.commit()
    assert n1 == n2
