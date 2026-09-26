from __future__ import annotations

from fastapi.testclient import TestClient

from app import main as main_module
from app.main import app


def test_lifespan_start_stop() -> None:
    with TestClient(app) as client:
        assert client.get("/api/v1/health/live").status_code == 200


def test_double_shutdown_safe() -> None:
    with TestClient(app):
        pass
    with TestClient(app):
        pass


def test_main_dispose_fails_health_still_disposed(monkeypatch) -> None:
    import app.db.session as db_session

    calls = {"main": 0, "health": 0}

    class _Engine:
        def __init__(self, label: str, fail: bool) -> None:
            self._label = label
            self._fail = fail

        def dispose(self) -> None:
            calls[self._label] += 1
            if self._fail:
                raise RuntimeError("boom")

    monkeypatch.setattr(
        db_session, "engine", _Engine("main", fail=True)
    )
    monkeypatch.setattr(
        db_session, "health_engine", _Engine("health", fail=False)
    )

    main_module._dispose("main", "app.db.session", "engine")
    main_module._dispose("health", "app.db.session", "health_engine")

    assert calls["main"] == 1
    assert calls["health"] == 1


def test_health_dispose_fails_main_still_disposed(monkeypatch) -> None:
    import app.db.session as db_session

    calls = {"main": 0, "health": 0}

    class _Engine:
        def __init__(self, label: str, fail: bool) -> None:
            self._label = label
            self._fail = fail

        def dispose(self) -> None:
            calls[self._label] += 1
            if self._fail:
                raise RuntimeError("boom")

    monkeypatch.setattr(
        db_session, "engine", _Engine("main", fail=False)
    )
    monkeypatch.setattr(
        db_session, "health_engine", _Engine("health", fail=True)
    )

    main_module._dispose("health", "app.db.session", "health_engine")
    main_module._dispose("main", "app.db.session", "engine")

    assert calls["health"] == 1
    assert calls["main"] == 1
