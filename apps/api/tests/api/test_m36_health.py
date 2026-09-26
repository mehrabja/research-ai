"""M36 — Liveness / readiness endpoint tests."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_live() -> None:
    r = client.get("/api/v1/health/live")
    assert r.status_code == 200
    assert r.json() == {"status": "alive"}


def test_live_does_not_require_db() -> None:
    """Liveness must return 200 even when the health DB is broken."""
    from sqlalchemy.exc import OperationalError

    from app.db.session import get_health_db

    class _BrokenSession:
        def execute(self, *_a: object, **_k: object) -> None:
            raise OperationalError("x", None, Exception("x"))

        def close(self) -> None:
            pass

    def _broken() -> object:
        yield _BrokenSession()

    app.dependency_overrides[get_health_db] = _broken
    try:
        r = client.get("/api/v1/health/live")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200


def test_ready_happy_path() -> None:
    r = client.get("/api/v1/health/ready")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "ready"
    assert body["checks"]["database"] == "ok"
    assert body["checks"]["queue"] == "ok"


def test_ready_returns_503_when_db_broken() -> None:
    from sqlalchemy.exc import OperationalError

    from app.db.session import get_health_db

    class _BrokenSession:
        def execute(self, *_a: object, **_k: object) -> None:
            raise OperationalError("x", None, Exception("x"))

        def close(self) -> None:
            pass

    def _broken() -> object:
        yield _BrokenSession()

    app.dependency_overrides[get_health_db] = _broken
    try:
        r = client.get("/api/v1/health/ready")
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 503
    body = r.json()
    assert body["status"] == "not_ready"
    assert body["checks"]["database"] == "unavailable"


def test_ready_does_not_leak_internals() -> None:
    from sqlalchemy.exc import OperationalError

    from app.db.session import get_health_db

    class _BrokenSession:
        def execute(self, *_a: object, **_k: object) -> None:
            raise OperationalError(
                "password=hunter2", None, Exception("boom")
            )

        def close(self) -> None:
            pass

    def _broken() -> object:
        yield _BrokenSession()

    app.dependency_overrides[get_health_db] = _broken
    try:
        r = client.get("/api/v1/health/ready")
    finally:
        app.dependency_overrides.clear()

    text = r.text
    assert "password" not in text
    assert "hunter2" not in text
    assert "Traceback" not in text
    assert "postgres" not in text.lower()
