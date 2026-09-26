"""Health endpoints (M36)."""
from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
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


@router.get("/health/live")
def health_live() -> dict[str, str]:
    """Liveness probe.

    Must NOT require the database, queue, storage, or any external
    dependency. Only proves the process is running and can respond.
    """
    return {"status": "alive"}


@router.get("/health/ready")
def health_ready(db: HealthDBSession) -> JSONResponse:
    """Readiness probe.

    In this repository the durable job queue is PostgreSQL-backed, so
    the "queue" probe is a cheap non-mutating schema-level check
    against the same database session. It is *not* a claim that the
    worker fleet is currently healthy.
    """
    checks: dict[str, str] = {}

    try:
        db.execute(text("SELECT 1")).scalar_one()
        checks["database"] = "ok"
    except SQLAlchemyError as exc:
        logger.warning(
            "readiness_database_failed err=%s",
            type(exc).__name__,
        )
        checks["database"] = "unavailable"

    if checks["database"] == "ok":
        try:
            db.execute(text("SELECT 1 FROM jobs LIMIT 1"))
            checks["queue"] = "ok"
        except SQLAlchemyError as exc:
            logger.warning(
                "readiness_queue_failed err=%s",
                type(exc).__name__,
            )
            checks["queue"] = "unavailable"
    else:
        checks["queue"] = "unknown"

    ready = all(v == "ok" for v in checks.values())
    return JSONResponse(
        status_code=200 if ready else 503,
        content={
            "status": "ready" if ready else "not_ready",
            "checks": checks,
        },
    )


@router.get("/health/db")
def health_db(db: HealthDBSession) -> dict[str, str]:
    try:
        db.execute(text("SELECT 1")).scalar_one()
    except SQLAlchemyError as exc:
        logger.exception("Database health check failed")
        raise DatabaseUnavailable() from exc

    return {"status": "ok", "database": "ok"}
