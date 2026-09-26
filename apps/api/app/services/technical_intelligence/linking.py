"""M29 — Deterministic code ↔ experiment linking."""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.technical_fact import TechnicalFact
from app.domain.technical_intelligence import TechnicalFactType


def _norm(name: str) -> str:
    return "".join(
        c if c.isalnum() else "_" for c in name.lower()
    ).strip("_")


def build_algorithm_index(
    db: Session, *, run_id: uuid.UUID,
) -> dict[str, uuid.UUID]:
    rows = list(db.execute(
        select(TechnicalFact.id, TechnicalFact.fact_key).where(
            TechnicalFact.technical_intelligence_run_id == run_id,
            TechnicalFact.fact_type
            == TechnicalFactType.ALGORITHM.value,
            TechnicalFact.status.in_(("extracted", "validated")),
        )
    ).all())
    idx: dict[str, uuid.UUID] = {}
    for fid, fkey in rows:
        if fkey:
            idx.setdefault(_norm(fkey), fid)
    return idx


def link_experiment_to_algorithm(
    *,
    algorithm_index: dict[str, uuid.UUID],
    experiment_key: str | None,
    value_row: dict | None,
) -> uuid.UUID | None:
    if experiment_key:
        k = _norm(experiment_key)
        if k in algorithm_index:
            return algorithm_index[k]
    if value_row:
        for v in value_row.values():
            if isinstance(v, str):
                k = _norm(v)
                if k in algorithm_index:
                    return algorithm_index[k]
    return None


__all__ = ["build_algorithm_index", "link_experiment_to_algorithm"]
