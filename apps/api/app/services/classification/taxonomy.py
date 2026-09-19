"""M21 — Taxonomy lookup helpers."""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ClassificationTaxonomyNotFound
from app.db.models.research_taxonomy import (
    PaperType,
    ResearchDesign,
    ResearchDomain,
)


def get_domain_by_code(
    db: Session, *, code: str
) -> ResearchDomain | None:
    return db.execute(
        select(ResearchDomain).where(
            ResearchDomain.code == code,
            ResearchDomain.is_active.is_(True),
        )
    ).scalar_one_or_none()


def get_paper_type(
    db: Session, *, code: str
) -> PaperType | None:
    return db.execute(
        select(PaperType).where(
            PaperType.code == code,
            PaperType.is_active.is_(True),
        )
    ).scalar_one_or_none()


def get_research_design(
    db: Session, *, code: str
) -> ResearchDesign | None:
    return db.execute(
        select(ResearchDesign).where(
            ResearchDesign.code == code,
            ResearchDesign.is_active.is_(True),
        )
    ).scalar_one_or_none()


def require_domain(
    db: Session, *, code: str
) -> ResearchDomain:
    dom = get_domain_by_code(db, code=code)
    if dom is None:
        raise ClassificationTaxonomyNotFound(
            f"domain code {code!r} not found or inactive"
        )
    return dom


def require_paper_type(
    db: Session, *, code: str
) -> PaperType:
    pt = get_paper_type(db, code=code)
    if pt is None:
        raise ClassificationTaxonomyNotFound(
            f"paper_type code {code!r} not found or inactive"
        )
    return pt


def require_research_design(
    db: Session, *, code: str
) -> ResearchDesign:
    rd = get_research_design(db, code=code)
    if rd is None:
        raise ClassificationTaxonomyNotFound(
            f"research_design code {code!r} not found or inactive"
        )
    return rd


def list_active_domains(db: Session) -> list[ResearchDomain]:
    return list(
        db.execute(
            select(ResearchDomain)
            .where(ResearchDomain.is_active.is_(True))
            .order_by(ResearchDomain.depth, ResearchDomain.code)
        )
        .scalars()
        .all()
    )


def resolve_domain_id_by_code(
    db: Session, *, code: str
) -> uuid.UUID | None:
    dom = get_domain_by_code(db, code=code)
    return dom.id if dom else None
