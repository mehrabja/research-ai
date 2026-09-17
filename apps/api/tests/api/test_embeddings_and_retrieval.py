"""Embedding + retrieval API tests.

The provider is monkeypatched. No live HTTP calls are made.
"""
from __future__ import annotations

import uuid
from collections.abc import Iterator, Sequence

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select, text

from app.db.models.report import Report, ReportEvent
from app.db.models.source import Chunk, Source
from app.db.models.user import User
from app.db.session import SessionLocal
from app.domain.embeddings import (
    EmbeddingBatchResult,
    EmbeddingProfile,
    EmbeddingUsage,
)
from app.main import app
from app.services.rate_limit import set_login_rate_limiter

client = TestClient(app)


# ===========================================================================
# Fixtures
# ===========================================================================
@pytest.fixture(autouse=True)
def fresh_rate_limiter() -> Iterator[None]:
    set_login_rate_limiter(None)
    yield
    set_login_rate_limiter(None)


@pytest.fixture()
def cleanup_users() -> Iterator[list[uuid.UUID]]:
    user_ids: list[uuid.UUID] = []
    yield user_ids
    if not user_ids:
        return

    from app.db.models.ops import UsageLog

    with SessionLocal() as db:
        report_ids_subq = select(Report.id).where(
            Report.user_id.in_(user_ids)
        )
        source_ids_subq = select(Source.id).where(
            Source.report_id.in_(report_ids_subq)
        )
        db.execute(
            delete(UsageLog).where(UsageLog.user_id.in_(user_ids))
        )
        db.execute(
            delete(Chunk).where(Chunk.source_id.in_(source_ids_subq))
        )
        db.execute(
            delete(ReportEvent).where(
                ReportEvent.report_id.in_(report_ids_subq)
            )
        )
        db.execute(
            delete(Source).where(Source.report_id.in_(report_ids_subq))
        )
        db.execute(delete(Report).where(Report.user_id.in_(user_ids)))
        db.execute(delete(User).where(User.id.in_(user_ids)))
        db.commit()


def _register_and_login(
    cleanup_users: list[uuid.UUID],
) -> tuple[uuid.UUID, str]:
    email = f"m9-{uuid.uuid4().hex}@example.com"
    password = "Correct Horse Battery Staple!"
    r = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password},
    )
    assert r.status_code == 201, r.text
    user_id = uuid.UUID(r.json()["id"])
    cleanup_users.append(user_id)
    r = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert r.status_code == 200, r.text
    return user_id, r.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_report(token: str) -> dict:
    r = client.post(
        "/api/v1/reports",
        headers=_auth(token),
        json={"topic": "T", "output_language": "en"},
    )
    assert r.status_code == 201, r.text
    return r.json()


def _seed_source_and_chunks(
    *, report_id: uuid.UUID, chunks: list[str]
) -> uuid.UUID:
    with SessionLocal() as db:
        sid = db.execute(
            text(
                "INSERT INTO sources "
                "(report_id, title, status) "
                "VALUES (:r, 'T', 'full_text') RETURNING id"
            ),
            {"r": report_id},
        ).scalar()
        for idx, content in enumerate(chunks):
            db.execute(
                text(
                    "INSERT INTO chunks "
                    "(source_id, content, chunk_index, embedding_status) "
                    "VALUES (:s, :c, :i, 'pending')"
                ),
                {"s": sid, "c": content, "i": idx},
            )
        db.commit()
    return sid


# ===========================================================================
# Fake provider
# ===========================================================================
class _FakeProvider:
    provider_name = "openai"
    model_name = "text-embedding-3-small"
    dimensions = 1536
    max_batch_size = 64
    max_input_tokens_per_item = 8191
    max_input_tokens_per_request = 300_000

    def estimate_input_tokens(self, text: str) -> int | None:
        return len(text)

    def embed_documents(
        self, texts: Sequence[str]
    ) -> EmbeddingBatchResult:
        return EmbeddingBatchResult(
            vectors=[[0.1] * 1536 for _ in texts],
            usage=EmbeddingUsage(
                input_tokens=sum(len(t) for t in texts),
                request_count=1,
            ),
        )

    def embed_query(self, text: str) -> list[float]:
        return [0.1] * 1536


def _patch_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    """Swap the OpenAI adapter for a deterministic fake.

    The route module binds ``build_embedding_provider`` at import time
    via ``from app.services.embedding_profile import ...``. We must
    patch it in the route module's namespace, not in the source module.
    """
    import app.api.routes.embeddings as route_mod

    def _factory(
        _profile: EmbeddingProfile | None = None,
    ) -> _FakeProvider:
        return _FakeProvider()

    monkeypatch.setattr(
        route_mod, "build_embedding_provider", _factory
    )


# ===========================================================================
# Auth
# ===========================================================================
def test_embed_requires_auth() -> None:
    r = client.post(
        f"/api/v1/reports/{uuid.uuid4()}"
        f"/sources/{uuid.uuid4()}/embed"
    )
    assert r.status_code == 401


def test_retrieve_requires_auth() -> None:
    r = client.post(
        f"/api/v1/reports/{uuid.uuid4()}/retrieve",
        json={"query": "x"},
    )
    assert r.status_code == 401


# ===========================================================================
# Ownership
# ===========================================================================
def test_embed_foreign_report_404(
    cleanup_users: list[uuid.UUID],
) -> None:
    _, token_a = _register_and_login(cleanup_users)
    _, token_b = _register_and_login(cleanup_users)
    report_b = _create_report(token_b)
    sid = _seed_source_and_chunks(
        report_id=uuid.UUID(report_b["id"]), chunks=["x"]
    )
    r = client.post(
        f"/api/v1/reports/{report_b['id']}/sources/{sid}/embed",
        headers=_auth(token_a),
    )
    assert r.status_code == 404


def test_retrieve_foreign_report_404(
    cleanup_users: list[uuid.UUID],
) -> None:
    _, token_a = _register_and_login(cleanup_users)
    _, token_b = _register_and_login(cleanup_users)
    report_b = _create_report(token_b)
    _seed_source_and_chunks(
        report_id=uuid.UUID(report_b["id"]), chunks=["hello world"]
    )
    r = client.post(
        f"/api/v1/reports/{report_b['id']}/retrieve",
        headers=_auth(token_a),
        json={"query": "hello"},
    )
    assert r.status_code == 404


# ===========================================================================
# Embed happy path
# ===========================================================================
def test_embed_source_success(
    cleanup_users: list[uuid.UUID],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_provider(monkeypatch)
    _, token = _register_and_login(cleanup_users)
    report = _create_report(token)
    sid = _seed_source_and_chunks(
        report_id=uuid.UUID(report["id"]),
        chunks=["alpha", "beta", "gamma"],
    )
    r = client.post(
        f"/api/v1/reports/{report['id']}/sources/{sid}/embed",
        headers=_auth(token),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["embedded"] == 3
    assert body["total_chunks"] == 3
    assert body["already_current"] == 0
    assert body["failed"] == 0

    with SessionLocal() as db:
        with_emb = db.execute(
            text(
                "SELECT count(*) FROM chunks "
                "WHERE source_id = :s AND embedding IS NOT NULL"
            ),
            {"s": sid},
        ).scalar()
    assert with_emb == 3


# ===========================================================================
# Retrieval readiness
# ===========================================================================
def test_retrieval_lexical_works_without_embeddings(
    cleanup_users: list[uuid.UUID],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_provider(monkeypatch)
    _, token = _register_and_login(cleanup_users)
    report = _create_report(token)
    _seed_source_and_chunks(
        report_id=uuid.UUID(report["id"]),
        chunks=["the quick brown fox", "a slow lazy dog"],
    )
    r = client.post(
        f"/api/v1/reports/{report['id']}/retrieve",
        headers=_auth(token),
        json={"query": "quick fox", "mode": "lexical"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["coverage"]["embedded_chunks"] == 0
    assert len(body["results"]) >= 1


def test_retrieval_semantic_requires_embeddings(
    cleanup_users: list[uuid.UUID],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_provider(monkeypatch)
    _, token = _register_and_login(cleanup_users)
    report = _create_report(token)
    _seed_source_and_chunks(
        report_id=uuid.UUID(report["id"]), chunks=["hello world"]
    )
    r = client.post(
        f"/api/v1/reports/{report['id']}/retrieve",
        headers=_auth(token),
        json={"query": "hello", "mode": "semantic"},
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "EMBEDDINGS_NOT_READY"


# ===========================================================================
# End-to-end: embed then retrieve
# ===========================================================================
def test_embed_then_retrieve_hybrid(
    cleanup_users: list[uuid.UUID],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_provider(monkeypatch)
    _, token = _register_and_login(cleanup_users)
    report = _create_report(token)
    sid = _seed_source_and_chunks(
        report_id=uuid.UUID(report["id"]),
        chunks=[
            "the quick brown fox jumps over the lazy dog",
            "a second unrelated chunk of text",
        ],
    )
    r = client.post(
        f"/api/v1/reports/{report['id']}/sources/{sid}/embed",
        headers=_auth(token),
    )
    assert r.status_code == 200, r.text

    r = client.post(
        f"/api/v1/reports/{report['id']}/retrieve",
        headers=_auth(token),
        json={"query": "quick fox", "mode": "hybrid", "top_k": 5},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["coverage"]["embedded_chunks"] == 2
    assert len(body["results"]) >= 1
    assert body["retrieval_algorithm_version"] == "m9.1"
