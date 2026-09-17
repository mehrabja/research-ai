"""Token-aware batch construction tests."""
from __future__ import annotations

import uuid
from collections.abc import Sequence

from app.db.models.source import Chunk
from app.domain.embeddings import EmbeddingBatchResult
from app.services.embeddings import _build_batches


class _TokProvider:
    provider_name = "fake"
    model_name = "fake"
    dimensions = 3
    max_batch_size = 100
    max_input_tokens_per_item = 100
    max_input_tokens_per_request = 250

    def estimate_input_tokens(self, text: str) -> int | None:
        return len(text)

    def embed_documents(
        self, texts: Sequence[str]
    ) -> EmbeddingBatchResult:
        raise NotImplementedError

    def embed_query(self, text: str) -> list[float]:
        raise NotImplementedError


class _NoTokProvider(_TokProvider):
    def estimate_input_tokens(self, text: str) -> int | None:
        return None


def _chunk(text: str) -> Chunk:
    c = Chunk()
    c.id = uuid.uuid4()
    c.content = text
    return c


def test_token_budget_respected() -> None:
    p = _TokProvider()
    chunks = [_chunk("a" * 100), _chunk("b" * 100), _chunk("c" * 100)]
    batches = _build_batches(chunks, provider=p, max_items=10)
    assert [len(b) for b in batches] == [2, 1]


def test_item_limit_respected() -> None:
    p = _TokProvider()
    p.max_batch_size = 2
    chunks = [_chunk("a") for _ in range(5)]
    batches = _build_batches(chunks, provider=p, max_items=10)
    assert [len(b) for b in batches] == [2, 2, 1]


def test_no_tokenizer_uses_safe_item_cap() -> None:
    p = _NoTokProvider()
    chunks = [_chunk("x" * 100) for _ in range(5)]
    batches = _build_batches(chunks, provider=p, max_items=10)
    assert all(len(b) <= 2 for b in batches)
    assert sum(len(b) for b in batches) == 5
