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
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import Connection, Engine

REPO_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(REPO_ROOT / ".env", override=False)


def _db_url() -> str:
    url = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL")
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
