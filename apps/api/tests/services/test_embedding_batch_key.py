"""Batch idempotency key tests."""
from __future__ import annotations

import uuid

from app.db.models.source import Chunk
from app.services.embeddings import build_embedding_batch_idempotency_key


def _chunk(content: str, cid: uuid.UUID | None = None) -> Chunk:
    c = Chunk()
    c.id = cid or uuid.uuid4()
    c.content = content
    return c


def test_same_chunks_same_key_order_independent() -> None:
    rid, sid = uuid.uuid4(), uuid.uuid4()
    a, b = _chunk("alpha"), _chunk("beta")
    k1 = build_embedding_batch_idempotency_key(
        report_id=rid, source_id=sid, provider="openai",
        model="m", profile_id="p", batch=[a, b],
    )
    k2 = build_embedding_batch_idempotency_key(
        report_id=rid, source_id=sid, provider="openai",
        model="m", profile_id="p", batch=[b, a],
    )
    assert k1 == k2


def test_changed_content_changes_key() -> None:
    rid, sid = uuid.uuid4(), uuid.uuid4()
    a = _chunk("alpha")
    a_prime = _chunk("alpha-modified", cid=a.id)
    k1 = build_embedding_batch_idempotency_key(
        report_id=rid, source_id=sid, provider="openai",
        model="m", profile_id="p", batch=[a],
    )
    k2 = build_embedding_batch_idempotency_key(
        report_id=rid, source_id=sid, provider="openai",
        model="m", profile_id="p", batch=[a_prime],
    )
    assert k1 != k2


def test_different_profile_changes_key() -> None:
    rid, sid = uuid.uuid4(), uuid.uuid4()
    a = _chunk("alpha")
    k1 = build_embedding_batch_idempotency_key(
        report_id=rid, source_id=sid, provider="openai",
        model="m", profile_id="p1", batch=[a],
    )
    k2 = build_embedding_batch_idempotency_key(
        report_id=rid, source_id=sid, provider="openai",
        model="m", profile_id="p2", batch=[a],
    )
    assert k1 != k2
