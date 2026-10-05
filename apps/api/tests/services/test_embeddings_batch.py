"""Pure unit tests for embedding batch invocation contracts."""
from __future__ import annotations

import uuid

from app.db.models.source import Chunk
from app.domain.embeddings import EmbeddingBatchResult, EmbeddingUsage
from app.services.embeddings import _embed_documents_for_batch


class _FakeEmbeddingProvider:
    provider_name = "fake"
    model_name = "fake-model"
    dimensions = 3
    max_batch_size = 10
    max_input_tokens_per_item = None
    max_input_tokens_per_request = None

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def estimate_input_tokens(self, text: str) -> int | None:
        return len(text)

    def embed_documents(self, texts: list[str]) -> EmbeddingBatchResult:
        self.calls.append(list(texts))
        return EmbeddingBatchResult(
            vectors=[[0.0, 0.0, 0.0] for _ in texts],
            usage=EmbeddingUsage(input_tokens=sum(len(text) for text in texts)),
        )

    def embed_query(self, text: str) -> list[float]:
        return [0.0, 0.0, 0.0]


def _chunk(content: str, index: int) -> Chunk:
    return Chunk(
        source_id=uuid.uuid4(),
        content=content,
        chunk_index=index,
    )


def test_embed_documents_for_batch_binds_exact_batch() -> None:
    provider = _FakeEmbeddingProvider()
    batch = [_chunk("first", 0), _chunk("second", 1)]

    result = _embed_documents_for_batch(provider, batch)

    assert provider.calls == [["first", "second"]]
    assert len(result.vectors) == 2
    assert result.usage.input_tokens == len("first") + len("second")
