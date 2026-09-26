"""M30 — prose adapter behavior (post-M28.5)."""
from __future__ import annotations

import uuid

from app.db.session import SessionLocal
from app.services.citation import prose as prose_svc


def test_get_manuscript_prose_returns_none_for_unknown_version() -> None:
    """When no M28.5 run exists for the manuscript version, the
    adapter returns None (fail-closed)."""
    with SessionLocal() as db:
        result = prose_svc.get_manuscript_prose(
            db, manuscript_version_id=uuid.uuid4(),
        )
    assert result is None
