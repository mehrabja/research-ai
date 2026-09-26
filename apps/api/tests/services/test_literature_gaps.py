"""M23 — Gap detection tests."""
from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import delete, select

from app.core.config import get_settings
from app.db.models.literature import (
    LiteratureCluster,
    LiteratureGap,
    ProjectLiteratureItem,
)
from app.db.models.project import Project, ProjectEvent
from app.db.models.report import Report
from app.db.models.source import Source
from app.db.models.user import User
from app.db.models.workspace import Workspace
from app.db.session import SessionLocal
from app.services import projects as projects_service
from app.services.literature import gaps as gaps_service


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
            delete(LiteratureGap).where(
                LiteratureGap.project_id.in_(pids)
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
                email=f"lit-gp-{uid.hex[:8]}@e.com",
                password_hash="x",
            )
        )
        db.commit()
    uids.append(uid)
    return uid


def test_evidence_gap_when_no_sources(cleanup_users):
    uid = _mk_user(cleanup_users)
    with SessionLocal() as db:
        p = projects_service.create_project(db, user_id=uid, name="P")
        pid = p.id

    with SessionLocal() as db:
        count = gaps_service.detect_project_gaps(
            db, project_id=pid, sources_by_id={}
        )
        db.commit()
    assert count >= 1
    with SessionLocal() as db:
        rows = list(
            db.execute(
                select(LiteratureGap).where(
                    LiteratureGap.project_id == pid
                )
            ).scalars().all()
        )
    assert any(g.gap_type == "evidence_gap" for g in rows)


def test_contradiction_gap_from_cluster(cleanup_users):
    uid = _mk_user(cleanup_users)
    with SessionLocal() as db:
        p = projects_service.create_project(db, user_id=uid, name="P")
        c = LiteratureCluster(
            project_id=p.id,
            name="X",
            cluster_method="m",
            cluster_version="v",
            source_count=2,
            status="completed",
            disagreements=[
                {
                    "claim_a": "effective",
                    "claim_b": "no effect",
                    "source_a": str(uuid.uuid4()),
                    "source_b": str(uuid.uuid4()),
                    "confidence": 0.5,
                }
            ],
        )
        db.add(c)
        db.commit()
        pid = p.id

    with SessionLocal() as db:
        gaps_service.detect_project_gaps(
            db, project_id=pid, sources_by_id={}
        )
        db.commit()
    with SessionLocal() as db:
        rows = list(
            db.execute(
                select(LiteratureGap).where(
                    LiteratureGap.project_id == pid,
                    LiteratureGap.gap_type == "contradiction_gap",
                )
            ).scalars().all()
        )
    assert len(rows) == 1
    assert rows[0].supporting_source_ids


def test_preserved_gap_dedup_by_fingerprint(cleanup_users):
    """An accepted gap is preserved and suppresses candidate recreation."""
    uid = _mk_user(cleanup_users)
    with SessionLocal() as db:
        p = projects_service.create_project(db, user_id=uid, name="P")
        pid = p.id

    with SessionLocal() as db:
        gaps_service.detect_project_gaps(
            db, project_id=pid, sources_by_id={}
        )
        db.commit()

    with SessionLocal() as db:
        rows = list(
            db.execute(
                select(LiteratureGap).where(
                    LiteratureGap.project_id == pid
                )
            ).scalars().all()
        )
        assert len(rows) >= 1
        rows[0].status = "accepted"
        db.commit()
        accepted_fp = rows[0].fingerprint

    with SessionLocal() as db:
        gaps_service.detect_project_gaps(
            db, project_id=pid, sources_by_id={}
        )
        db.commit()

    with SessionLocal() as db:
        rows2 = list(
            db.execute(
                select(LiteratureGap).where(
                    LiteratureGap.project_id == pid,
                    LiteratureGap.fingerprint == accepted_fp,
                )
            ).scalars().all()
        )
        assert len(rows2) == 1
        assert rows2[0].status == "accepted"
