"""Handler-level tests for embedding_source.

The M9 embedding service is mocked. No provider is called.
"""
from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from sqlalchemy import text

from app.db.session import SessionLocal
from app.domain.jobs import JobContext


def _mk_job_and_user() -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    with SessionLocal() as db:
        uid = db.execute(
            text(
                "INSERT INTO users (email, password_hash) "
                "VALUES (:e, 'h') RETURNING id"
            ),
            {"e": f"eh-{uuid.uuid4().hex}@example.com"},
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
                "INSERT INTO sources (report_id, title, status) "
                "VALUES (:r, 'T', 'full_text') RETURNING id"
            ),
            {"r": rid},
        ).scalar()
        jid = db.execute(
            text(
                "INSERT INTO jobs "
                "(job_type, status, payload, user_id, report_id, "
                " attempt_count, max_attempts, worker_id, "
                " heartbeat_at, started_at) "
                "VALUES ('embedding_source', 'processing', "
                "        CAST(:p AS jsonb), :u, :r, 1, 3, 'w-test', "
                "        now(), now()) RETURNING id"
            ),
            {
                "p": (
                    f'{{"report_id":"{rid}","source_id":"{sid}"}}'
                ),
                "u": uid,
                "r": rid,
            },
        ).scalar()
        db.commit()
    return jid, rid, sid


def _ctx(
    job_id: uuid.UUID, report_id: uuid.UUID, source_id: uuid.UUID
) -> JobContext:
    return JobContext(
        job_id=job_id,
        job_type="embedding_source",
        attempt_count=1,
        worker_id="w-test",
        payload={
            "report_id": str(report_id),
            "source_id": str(source_id),
        },
    )


def test_missing_report_id_raises() -> None:
    from app.workers.handlers import (
        InvalidEmbeddingPayloadError,
        _embedding_source,
    )

    ctx = JobContext(
        job_id=uuid.uuid4(),
        job_type="embedding_source",
        attempt_count=1,
        worker_id="w-test",
        payload={"source_id": str(uuid.uuid4())},
    )
    with pytest.raises(InvalidEmbeddingPayloadError):
        _embedding_source(ctx)


def test_missing_source_id_raises() -> None:
    from app.workers.handlers import (
        InvalidEmbeddingPayloadError,
        _embedding_source,
    )

    ctx = JobContext(
        job_id=uuid.uuid4(),
        job_type="embedding_source",
        attempt_count=1,
        worker_id="w-test",
        payload={"report_id": str(uuid.uuid4())},
    )
    with pytest.raises(InvalidEmbeddingPayloadError):
        _embedding_source(ctx)


def test_invalid_uuid_raises() -> None:
    from app.workers.handlers import (
        InvalidEmbeddingPayloadError,
        _embedding_source,
    )

    ctx = JobContext(
        job_id=uuid.uuid4(),
        job_type="embedding_source",
        attempt_count=1,
        worker_id="w-test",
        payload={"report_id": "not-a-uuid", "source_id": "x"},
    )
    with pytest.raises(InvalidEmbeddingPayloadError):
        _embedding_source(ctx)


def test_valid_payload_calls_m9_service() -> None:
    from app.services.embeddings import EmbeddingRunResult
    from app.workers.handlers import _embedding_source

    jid, rid, sid = _mk_job_and_user()
    ctx = _ctx(jid, rid, sid)

    fake_result = EmbeddingRunResult(
        source_id=sid,
        total_chunks=3,
        already_current=0,
        embedded=3,
        failed=0,
        pending=0,
        profile_id="openai/text-embedding-3-small:1536:cosine:m9.1",
        usage_input_tokens=42,
    )

    with patch(
        "app.workers.handlers.embeddings_service.embed_source",
        return_value=fake_result,
    ) as mock_embed:
        _embedding_source(ctx)

    assert mock_embed.call_count == 1
    call_kwargs = mock_embed.call_args.kwargs
    assert call_kwargs["report_id"] == rid
    assert call_kwargs["source_id"] == sid


def test_retryable_provider_error_propagates() -> None:
    from app.integrations.embeddings.base import (
        EmbeddingRateLimitError,
    )
    from app.workers.handlers import _embedding_source

    jid, rid, sid = _mk_job_and_user()
    ctx = _ctx(jid, rid, sid)

    with patch(
        "app.workers.handlers.embeddings_service.embed_source",
        side_effect=EmbeddingRateLimitError("rl"),
    ), pytest.raises(EmbeddingRateLimitError):
        _embedding_source(ctx)


def test_partial_result_raises_retryable() -> None:
    from app.integrations.embeddings.base import (
        EmbeddingProviderUnavailableError,
    )
    from app.services.embeddings import EmbeddingRunResult
    from app.workers.handlers import _embedding_source

    jid, rid, sid = _mk_job_and_user()
    ctx = _ctx(jid, rid, sid)

    partial = EmbeddingRunResult(
        source_id=sid,
        total_chunks=5,
        already_current=0,
        embedded=3,
        failed=2,
        pending=0,
        profile_id="p",
        usage_input_tokens=10,
    )

    with patch(
        "app.workers.handlers.embeddings_service.embed_source",
        return_value=partial,
    ), pytest.raises(EmbeddingProviderUnavailableError):
        _embedding_source(ctx)
