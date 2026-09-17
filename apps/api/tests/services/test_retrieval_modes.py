"""Mode-dependent readiness for retrieval."""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

from app.core.exceptions import EmbeddingsNotReadyError
from app.db.session import SessionLocal
from app.domain.embeddings import EmbeddingProfile
from app.services import retrieval as retrieval_service


def _profile() -> EmbeddingProfile:
    return EmbeddingProfile(
        provider="fake",
        model="fake-model",
        dimensions=3,
        distance_metric="cosine",
        profile_version="test",
    )


class _NoOpProvider:
    provider_name = "fake"
    model_name = "fake-model"
    dimensions = 3
    max_batch_size = 10
    max_input_tokens_per_item = 1000
    max_input_tokens_per_request = 10000

    def estimate_input_tokens(self, text: str) -> int | None:
        return None

    def embed_documents(self, texts):  # type: ignore[no-untyped-def]
        raise AssertionError("must not be called in readiness tests")

    def embed_query(self, text: str) -> list[float]:
        raise AssertionError("must not be called in readiness tests")


def _seed_source_with_text_chunks() -> tuple[
    uuid.UUID, uuid.UUID, uuid.UUID
]:
    with SessionLocal() as db:
        uid = db.execute(
            text(
                "INSERT INTO users (email, password_hash) "
                "VALUES (:e, 'h') RETURNING id"
            ),
            {"e": f"retr-{uuid.uuid4().hex}@example.com"},
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
        for idx, content in enumerate(
            [
                "the quick brown fox jumps over the lazy dog",
                "a second chunk with different lexical content",
            ]
        ):
            db.execute(
                text(
                    "INSERT INTO chunks "
                    "(source_id, content, chunk_index, "
                    " embedding_status) "
                    "VALUES (:s, :c, :i, 'pending')"
                ),
                {"s": sid, "c": content, "i": idx},
            )
        db.commit()
    return uid, rid, sid


def test_lexical_succeeds_without_embeddings() -> None:
    uid, rid, _sid = _seed_source_with_text_chunks()
    with SessionLocal() as db:
        results, coverage = retrieval_service.retrieve(
            db,
            user_id=uid,
            report_id=rid,
            query="quick fox",
            top_k=5,
            mode="lexical",
            algorithm="exact",
            source_ids=None,
            provider=_NoOpProvider(),
            profile=_profile(),
        )
    assert coverage["embedded_chunks"] == 0
    assert coverage["total_chunks"] > 0
    assert len(results) >= 1


def test_semantic_raises_without_embeddings() -> None:
    uid, rid, _sid = _seed_source_with_text_chunks()
    with SessionLocal() as db, pytest.raises(EmbeddingsNotReadyError):
        retrieval_service.retrieve(
            db,
            user_id=uid,
            report_id=rid,
            query="quick fox",
            top_k=5,
            mode="semantic",
            algorithm="exact",
            source_ids=None,
            provider=_NoOpProvider(),
            profile=_profile(),
        )


def test_hybrid_raises_without_embeddings() -> None:
    uid, rid, _sid = _seed_source_with_text_chunks()
    with SessionLocal() as db, pytest.raises(EmbeddingsNotReadyError):
        retrieval_service.retrieve(
            db,
            user_id=uid,
            report_id=rid,
            query="quick fox",
            top_k=5,
            mode="hybrid",
            algorithm="exact",
            source_ids=None,
            provider=_NoOpProvider(),
            profile=_profile(),
        )
