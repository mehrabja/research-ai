"""M39 bootstrap regression tests for critical import/runtime entry points."""


def test_model_registry_imports():
    from app.db.models import UserSession

    assert UserSession.__tablename__ == "user_sessions"


def test_api_router_imports():
    from app.api.router import api_router

    assert api_router.routes


def test_worker_module_entrypoint_uses_runner():
    from app.workers.__main__ import main as entry_main
    from app.workers.runner import main as runner_main

    assert entry_main is runner_main
