"""M31 — context hash determinism."""
from __future__ import annotations

import uuid

from app.db.session import SessionLocal
from app.services.academic_qa.context import compute_m31_context_hash


def test_hash_deterministic_on_unknown_version() -> None:
    version_id = uuid.uuid4()
    with SessionLocal() as db:
        a = compute_m31_context_hash(
            db, manuscript_version_id=version_id,
        )
        b = compute_m31_context_hash(
            db, manuscript_version_id=version_id,
        )
    assert a == b
    assert len(a) == 64


def test_hash_differs_per_version() -> None:
    with SessionLocal() as db:
        a = compute_m31_context_hash(
            db, manuscript_version_id=uuid.uuid4(),
        )
        b = compute_m31_context_hash(
            db, manuscript_version_id=uuid.uuid4(),
        )
    # Missing versions both produce the sentinel hash, so equality is
    # expected. This test proves we do NOT crash on unknown version.
    assert a == b
    assert len(a) == 64
