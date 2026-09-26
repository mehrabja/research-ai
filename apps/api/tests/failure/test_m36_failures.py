"""M36 — bounded failure-scenario tests.

Uses TestClient with dependency overrides. None of these tests require
external services to be down.
"""
from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.db.session import get_health_db
from app.main import app

client = TestClient(app)


def test_db_down_readiness_returns_503() -> None:
    class _Broken:
        def execute(self, *_a, **_k):
            raise OperationalError("x", None, Exception("x"))

        def close(self) -> None:
            pass

    def _broken_db():
        yield _Broken()

    app.dependency_overrides[get_health_db] = _broken_db
    try:
        r = client.get("/api/v1/health/ready")
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 503
    assert r.json()["checks"]["database"] == "unavailable"


def test_db_down_liveness_still_ok() -> None:
    class _Broken:
        def execute(self, *_a, **_k):
            raise OperationalError("x", None, Exception("x"))

        def close(self) -> None:
            pass

    def _broken_db():
        yield _Broken()

    app.dependency_overrides[get_health_db] = _broken_db
    try:
        r = client.get("/api/v1/health/live")
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 200


def test_invalid_config_rejected_at_startup() -> None:
    """Invalid production settings must raise at Settings construction."""
    import pytest
    from pydantic import ValidationError

    from app.core.config import Settings

    with pytest.raises(ValidationError):
        Settings(
            app_env="production",
            debug=True,
            jwt_secret_key="x" * 64,
            database_url="postgresql+psycopg://t:t@localhost/t",
        )


def test_rate_limiter_backend_unavailable_returns_429() -> None:
    """When the limiter rejects, it must produce a safe 429."""
    from app.services.general_rate_limit import (
        set_rate_limit_backend,
    )

    class _AlwaysReject:
        def hit(self, key, *, limit, window_seconds):
            return (False, 30)

        def reset(self) -> None:
            pass

        def size(self) -> int:
            return 0

    from app.services.general_rate_limit import (
        get_rate_limit_backend,
    )

    original = get_rate_limit_backend()
    set_rate_limit_backend(_AlwaysReject())
    try:
        r = client.get("/api/v1/health/live")
    finally:
        set_rate_limit_backend(original)

    assert r.status_code == 429
    assert r.json()["error"]["code"] == "RATE_LIMITED"
