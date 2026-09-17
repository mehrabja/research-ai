"""Vectors + usage commit atomically per batch."""
from __future__ import annotations

import uuid
from collections.abc import Sequence

import pytest
from sqlalchemy import text

from app.db.session import SessionLocal
from app.domain.embeddings import (
    EmbeddingBatchResult,
    EmbeddingProfile,
    EmbeddingUsage,
)
from app.services.embeddings import embed_source


def _profile() -> EmbeddingProfile:
    return EmbeddingProfile(
        provider="fake",
        model="fake-model",
        dimensions=3,
        distance_metric="cosine",
        profile_version="test",
    )


class _FakeProvider:
    provider_name = "fake"
    model_name = "fake-model"
    dimensions = 3
    max_batch_size = 10
    max_input_tokens_per_item = 1000
    max_input_tokens_per_request = 10000

    def estimate_input_tokens(self, text: str) -> int | None:
        return len(text)

    def embed_documents(
        self, texts: Sequence[str]
    ) -> EmbeddingBatchResult:
        return EmbeddingBatchResult(
            vectors=[[0.1, 0.2, 0.3] for _ in texts],
            usage=EmbeddingUsage(
                input_tokens=sum(len(t) for t in texts),
                request_count=1,
            ),
        )

    def embed_query(self, text: str) -> list[float]:
        return [0.1, 0.2, 0.3]


def _seed() -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    with SessionLocal() as db:
        uid = db.execute(
            text(
                "INSERT INTO users (email, password_hash) "
                "VALUES (:e, 'h') RETURNING id"
            ),
            {"e": f"emb-at-{uuid.uuid4().hex}@example.com"},
        ).scalar()
        rid = db.execute(
            text(
                "INSERT INTO reports "
                "(user_id, topic, status, output_language) "
                "VALUES (:u, 'T', 'draft', 'en') RETURNING id"
            ),
            {"u": uid},
        ).scalar()
        sid = db.execute(
            text(
                "INSERT INTO sources "
                "(report_id, title, status) "
                "VALUES (:r, 'T', 'full_text') RETURNING id"
            ),
            {"r": rid},
        ).scalar()
        for idx in range(3):
            db.execute(
                text(
                    "INSERT INTO chunks "
                    "(source_id, content, chunk_index, embedding_status) "
                    "VALUES (:s, :c, :i, 'pending')"
                ),
                {"s": sid, "c": f"chunk-{idx}", "i": idx},
            )
        db.commit()
    return uid, rid, sid


def test_usage_failure_rolls_back_vectors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the UsageLog construction fails mid-batch, no vector
    may persist.

    We simulate the failure by patching ``UsageLog.__init__`` so it
    raises. Patching only the constructor keeps ``UsageLog.id``
    usable for the pre-flight SELECT in ``_persist_batch_atomic``.
    """
    uid, rid, sid = _seed()

    from app.db.models.ops import UsageLog as _RealUsageLog

    def _broken_init(
        self, *args, **kwargs
    ):  # type: ignore[no-untyped-def]
        raise RuntimeError("simulated usage insert failure")

    monkeypatch.setattr(_RealUsageLog, "__init__", _broken_init)

    with SessionLocal() as db, pytest.raises(RuntimeError):
        embed_source(
            db,
            user_id=uid,
            report_id=rid,
            source_id=sid,
            provider=_FakeProvider(),
            profile=_profile(),
        )

    with SessionLocal() as db:
        with_emb = db.execute(
            text(
                "SELECT count(*) FROM chunks "
                "WHERE source_id = :s AND embedding IS NOT NULL"
            ),
            {"s": sid},
        ).scalar()
        usage = db.execute(
            text(
                "SELECT count(*) FROM usage_logs "
                "WHERE report_id = :r AND phase = 'embedding'"
            ),
            {"r": rid},
        ).scalar()

    assert with_emb == 0
    assert usage == 0
