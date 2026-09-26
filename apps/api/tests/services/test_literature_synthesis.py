"""M23 — Cluster synthesis tests."""
from __future__ import annotations

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
from app.db.models.source import Source
from app.db.models.user import User
from app.db.models.workspace import Workspace
from app.db.session import SessionLocal
from app.services import projects as projects_service
from app.services.literature import synthesis


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
                email=f"lit-syn-{uid.hex[:8]}@e.com",
                password_hash="x",
            )
        )
        db.commit()
    uids.append(uid)
    return uid


def test_cluster_summary_generated(cleanup_users):
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
        s1 = Source(report_id=r.id, title="A", status="full_text")
        s2 = Source(report_id=r.id, title="B", status="full_text")
        db.add_all([s1, s2])
        db.flush()
        it1 = ProjectLiteratureItem(
            project_id=p.id,
            source_id=s1.id,
            screening_status="candidate",
            relevance_score=0.8,
            findings_summary="intervention was effective",
            keywords=["ml", "nlp"],
            themes=["deep learning"],
        )
        it2 = ProjectLiteratureItem(
            project_id=p.id,
            source_id=s2.id,
            screening_status="candidate",
            relevance_score=0.7,
            findings_summary="intervention improved results",
            keywords=["nlp"],
            themes=["deep learning"],
        )
        db.add_all([it1, it2])
        db.flush()
        c = LiteratureCluster(
            project_id=p.id,
            name="X",
            cluster_method="m",
            cluster_version="v",
            source_count=2,
            status="pending",
        )
        db.add(c)
        db.flush()
        db.add_all(
            [
                LiteratureClusterMember(
                    cluster_id=c.id, literature_item_id=it1.id
                ),
                LiteratureClusterMember(
                    cluster_id=c.id, literature_item_id=it2.id
                ),
            ]
        )
        db.commit()
        cid = c.id

    with SessionLocal() as db:
        c = db.get(LiteratureCluster, cid)
        synthesis.synthesize_cluster(db, cluster=c)
        db.commit()
        assert c.status == "completed"
        assert c.summary
        assert c.evidence_strength is not None
        assert "deep learning" in (c.themes or [])


def test_supporting_sources_preserved(cleanup_users):
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
        s1 = Source(report_id=r.id, title="A", status="full_text")
        db.add(s1)
        db.flush()
        it1 = ProjectLiteratureItem(
            project_id=p.id,
            source_id=s1.id,
            screening_status="candidate",
            relevance_score=0.9,
        )
        db.add(it1)
        db.flush()
        c = LiteratureCluster(
            project_id=p.id,
            name="X",
            cluster_method="m",
            cluster_version="v",
            source_count=1,
            status="pending",
        )
        db.add(c)
        db.flush()
        db.add(
            LiteratureClusterMember(
                cluster_id=c.id, literature_item_id=it1.id
            )
        )
        db.commit()
        cid = c.id
        sid = s1.id

    with SessionLocal() as db:
        c = db.get(LiteratureCluster, cid)
        synthesis.synthesize_cluster(db, cluster=c)
        db.commit()
        assert c.representative_source_ids
        assert str(sid) in c.representative_source_ids


def test_disagreements_detected(cleanup_users):
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
        s1 = Source(report_id=r.id, title="A", status="full_text")
        s2 = Source(report_id=r.id, title="B", status="full_text")
        db.add_all([s1, s2])
        db.flush()
        it1 = ProjectLiteratureItem(
            project_id=p.id,
            source_id=s1.id,
            screening_status="candidate",
            findings_summary="the intervention was effective",
        )
        it2 = ProjectLiteratureItem(
            project_id=p.id,
            source_id=s2.id,
            screening_status="candidate",
            findings_summary="there was no significant effect",
        )
        db.add_all([it1, it2])
        db.flush()
        c = LiteratureCluster(
            project_id=p.id,
            name="X",
            cluster_method="m",
            cluster_version="v",
            source_count=2,
            status="pending",
        )
        db.add(c)
        db.flush()
        db.add_all(
            [
                LiteratureClusterMember(
                    cluster_id=c.id, literature_item_id=it1.id
                ),
                LiteratureClusterMember(
                    cluster_id=c.id, literature_item_id=it2.id
                ),
            ]
        )
        db.commit()
        cid = c.id

    with SessionLocal() as db:
        c = db.get(LiteratureCluster, cid)
        synthesis.synthesize_cluster(db, cluster=c)
        db.commit()
        assert c.disagreements
        assert len(c.disagreements) == 1
