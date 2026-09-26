"""M29 — stale worker must skip without mutating state."""
from __future__ import annotations

import uuid
from types import SimpleNamespace

from app.workers.technical_intelligence_handlers import (
    handle_technical_intelligence,
)


def test_stale_context_skips() -> None:
    ctx = SimpleNamespace(payload={
        "project_id": str(uuid.uuid4()),
        "context_hash": "not-the-current-hash",
        "m29_version": "m29.1",
    })
    result = handle_technical_intelligence(ctx)
    assert result["skipped"] is True
    assert result["reason"] == "stale_context"


def test_stale_version_skips() -> None:
    ctx = SimpleNamespace(payload={
        "project_id": str(uuid.uuid4()),
        "context_hash": None,
        "m29_version": "m29-OLD",
    })
    result = handle_technical_intelligence(ctx)
    assert result["skipped"] is True
    assert result["reason"] == "stale_version"


def test_missing_project_id_raises() -> None:
    import pytest

    ctx = SimpleNamespace(payload={})
    with pytest.raises(ValueError, match="project_id"):
        handle_technical_intelligence(ctx)
