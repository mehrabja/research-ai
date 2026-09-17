"""Health endpoints."""
from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.exceptions import DatabaseUnavailable
from app.db.session import get_health_db

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])

HealthDBSession = Annotated[Session, Depends(get_health_db)]


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/db")
def health_db(db: HealthDBSession) -> dict[str, str]:
    try:
        db.execute(text("SELECT 1")).scalar_one()
    except SQLAlchemyError as exc:
        logger.exception("Database health check failed")
        raise DatabaseUnavailable() from exc

    return {"status": "ok", "database": "ok"}
