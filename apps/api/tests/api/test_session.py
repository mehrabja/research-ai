"""Session integration tests."""
from __future__ import annotations

from sqlalchemy import text

from app.db.session import SessionLocal, engine


def test_engine_can_connect() -> None:
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1")).scalar_one()

    assert result == 1


def test_session_local_can_execute() -> None:
    db = SessionLocal()

    try:
        result = db.execute(text("SELECT 1")).scalar_one()
        assert result == 1
    finally:
        db.close()
