"""Health endpoint tests."""
from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.db.session import get_health_db
from app.main import app

client = TestClient(app)


def test_health_returns_ok() -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_db_reaches_real_postgres() -> None:
    response = client.get("/api/v1/health/db")

    assert response.status_code == 200, response.text
    assert response.json() == {
        "status": "ok",
        "database": "ok",
    }


def test_health_db_returns_503_when_db_fails() -> None:
    """Simulate a broken DB via the dedicated health dependency."""

    class _BrokenSession:
        def execute(self, *_args: object, **_kwargs: object) -> None:
            raise OperationalError(
                "simulated",
                None,
                Exception("boom"),
            )

        def close(self) -> None:
            pass

    def _broken_db():
        yield _BrokenSession()

    app.dependency_overrides[get_health_db] = _broken_db

    try:
        response = client.get("/api/v1/health/db")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json() == {
        "error": {
            "code": "DATABASE_UNAVAILABLE",
            "message": "Database is unavailable.",
        }
    }


def test_health_db_failure_does_not_leak_details() -> None:
    class _BrokenSession:
        def execute(self, *_args: object, **_kwargs: object) -> None:
            raise OperationalError(
                "password=hunter2",
                None,
                Exception("boom"),
            )

        def close(self) -> None:
            pass

    def _broken_db():
        yield _BrokenSession()

    app.dependency_overrides[get_health_db] = _broken_db

    try:
        response = client.get("/api/v1/health/db")
    finally:
        app.dependency_overrides.clear()

    body = response.text

    assert "password" not in body
    assert "hunter2" not in body
    assert "Traceback" not in body
