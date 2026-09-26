"""M26 — Context hash feature-flag and provider identity tests."""
from __future__ import annotations

import os
import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import delete, select

from app.core.config import get_settings
from app.db.models.project import Project, ProjectEvent
from app.db.models.user import User
from app.db.models.workspace import Workspace
from app.db.session import SessionLocal
from app.domain.embeddings import EmbeddingProfile
from app.services import projects as projects_service
from app.services.rag import context_hash as ch_svc


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
            id=uid, email=f"rag-hash-{uid.hex[:8]}@e.com",
            password_hash="x",
        ))
        db.commit()
    uids.append(uid)
    return uid


def _mk_project(uid) -> uuid.UUID:
    with SessionLocal() as db:
        p = projects_service.create_project(
            db, user_id=uid, name="P"
        )
        return p.id


def _profile() -> EmbeddingProfile:
    return EmbeddingProfile(
        provider="openai",
        model="text-embedding-3-small",
        dimensions=1536,
        distance_metric="cosine",
        profile_version="m9.1",
    )


def _hash(db, pid, *, llm_decomp=False, llm_rerank=False):
    get_settings.cache_clear()
    os.environ["RAG_LLM_DECOMPOSITION_ENABLED"] = str(
        llm_decomp
    ).lower()
    os.environ["RAG_LLM_RERANK_ENABLED"] = str(llm_rerank).lower()
    get_settings.cache_clear()
    try:
        return ch_svc.compute_retrieval_context_hash(
            db,
            project_id=pid,
            report_id=None,
            query_hash="q",
            graph_version_id=None,
            plan_id=None,
            section_id=None,
            requirement_id=None,
            mode="lexical",
            algorithm="ann",
            filters={"mode": "lexical"},
            profile=_profile(),
            effective_graph_enabled=False,
            effective_memory_enabled=False,
            effective_diversity_enabled=False,
            effective_max_results=10,
            candidate_limit=20,
        )
    finally:
        os.environ.pop("RAG_LLM_DECOMPOSITION_ENABLED", None)
        os.environ.pop("RAG_LLM_RERANK_ENABLED", None)
        get_settings.cache_clear()


def test_llm_decomp_flag_changes_hash(cleanup_users):
    uid = _mk_user(cleanup_users)
    pid = _mk_project(uid)
    with SessionLocal() as db:
        h_off = _hash(db, pid, llm_decomp=False)
        h_on = _hash(db, pid, llm_decomp=True)
    assert h_off != h_on


def test_llm_rerank_flag_changes_hash(cleanup_users):
    uid = _mk_user(cleanup_users)
    pid = _mk_project(uid)
    with SessionLocal() as db:
        h_off = _hash(db, pid, llm_rerank=False)
        h_on = _hash(db, pid, llm_rerank=True)
    assert h_off != h_on


def test_same_flags_same_hash(cleanup_users):
    uid = _mk_user(cleanup_users)
    pid = _mk_project(uid)
    with SessionLocal() as db:
        h1 = _hash(db, pid)
        h2 = _hash(db, pid)
    assert h1 == h2
