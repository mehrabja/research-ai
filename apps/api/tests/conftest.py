"""Pytest fixtures for the database test suite.

The tests assume the target database has been migrated to head
(``alembic upgrade head``). They run against TEST_DATABASE_URL if set,
otherwise DATABASE_URL. Each test runs inside a transaction that is
rolled back on teardown, so the database is left clean.
"""
from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from dotenv import dotenv_values
from sqlalchemy import create_engine
from sqlalchemy.engine import Connection, Engine

REPO_ROOT = Path(__file__).resolve().parents[3]
_DOTENV_VALUES = dotenv_values(REPO_ROOT / ".env")


def _db_url() -> str:
    url = (
        os.getenv("TEST_DATABASE_URL")
        or os.getenv("DATABASE_URL")
        or _DOTENV_VALUES.get("TEST_DATABASE_URL")
        or _DOTENV_VALUES.get("DATABASE_URL")
    )
    if not url:
        pytest.skip("TEST_DATABASE_URL / DATABASE_URL not configured")
    return url


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    eng = create_engine(_db_url(), future=True)
    try:
        yield eng
    finally:
        eng.dispose()


@pytest.fixture()
def conn(engine: Engine) -> Iterator[Connection]:
    """Per-test connection wrapped in a transaction that is rolled back."""
    connection = engine.connect()
    trans = connection.begin()
    try:
        yield connection
    finally:
        trans.rollback()
        connection.close()
@pytest.fixture(autouse=True)
def _reset_m36_state() -> Iterator[None]:
    """Reset module-global M36 state between tests."""
    from app.services.general_rate_limit import (
        reset_rate_limit_backend,
    )
    from app.workers import stats as worker_stats

    from app.core.config import get_settings

    get_settings.cache_clear()
    reset_rate_limit_backend()
    worker_stats.reset()
    try:
        yield
    finally:
        reset_rate_limit_backend()
        worker_stats.reset()
        get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _deterministic_embedding_when_provider_is_unconfigured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Use local embeddings for credential-free tests; never call a provider."""
    from app.core.config import get_settings
    from app.domain.embeddings import EmbeddingBatchResult, EmbeddingUsage

    settings = get_settings()
    if settings.app_env.lower() != "test":
        return
    if settings.openrouter_api_key.strip() or settings.embedding_openai_api_key.strip():
        return

    import hashlib
    import math

    import app.services.provider_registry as provider_registry

    class DeterministicEmbeddingProvider:
        def __init__(self, provider_name: str, profile: object) -> None:
            self.provider_name = provider_name
            self.model_name = str(getattr(profile, "model"))
            self.dimensions = int(getattr(profile, "dimensions"))
            self.max_batch_size = 64
            self.max_input_tokens_per_item = 8191
            self.max_input_tokens_per_request = 300_000

        def estimate_input_tokens(self, text: str) -> int:
            return len(text)

        def _embed(self, text: str) -> list[float]:
            raw = hashlib.shake_256(text.encode("utf-8")).digest(
                self.dimensions * 2
            )
            values = [
                ((raw[i * 2] * 256 + raw[i * 2 + 1]) / 32767.5) - 1.0
                for i in range(self.dimensions)
            ]
            norm = math.sqrt(sum(value * value for value in values)) or 1.0
            return [value / norm for value in values]

        def embed_documents(self, texts: list[str]) -> EmbeddingBatchResult:
            return EmbeddingBatchResult(
                vectors=[self._embed(value) for value in texts],
                usage=EmbeddingUsage(
                    input_tokens=sum(len(value) for value in texts),
                    request_count=1,
                ),
            )

        def embed_query(self, text: str) -> list[float]:
            return self._embed(text)

    def _build_test_embedding_provider(provider_name: str, profile: object):
        return DeterministicEmbeddingProvider(provider_name, profile)

    monkeypatch.setattr(
        provider_registry,
        "_build_embedding",
        _build_test_embedding_provider,
    )
