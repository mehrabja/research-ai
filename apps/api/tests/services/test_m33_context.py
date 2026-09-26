"""M33 — context hash determinism."""
from __future__ import annotations

import uuid

from app.db.session import SessionLocal
from app.services.publication.context import compute_m33_context_hash


def test_context_hash_missing_version() -> None:
    with SessionLocal() as db:
        a = compute_m33_context_hash(
            db,
            manuscript_version_id=uuid.uuid4(),
            target_id=uuid.uuid4(),
        )
        b = compute_m33_context_hash(
            db,
            manuscript_version_id=uuid.uuid4(),
            target_id=uuid.uuid4(),
        )
    # Missing inputs produce deterministic sentinel hashes.
    assert len(a) == 64
    assert len(b) == 64
    assert a == b
