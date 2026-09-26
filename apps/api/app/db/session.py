"""SQLAlchemy engine, session factories, and FastAPI dependencies.

M36 pool configuration:
  * pool_size / max_overflow  - bounded connection pool
  * pool_timeout              - bounded wait for a connection
  * pool_recycle              - proactive connection recycling
  * pool_pre_ping             - cheap dead-connection detection
  * connect_timeout           - bounded TCP connect
  * statement_timeout         - bounded per-statement execution

The dedicated ``health_engine`` keeps ``NullPool`` so readiness probes
never accumulate connections and never reuse stale sockets.
"""
from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from app.core.config import get_settings

_settings = get_settings()


def _build_main_connect_args() -> dict[str, object]:
    args: dict[str, object] = {
        "connect_timeout": _settings.db_connect_timeout_seconds,
    }
    if _settings.db_statement_timeout_ms > 0:
        args["options"] = (
            f"-c statement_timeout="
            f"{_settings.db_statement_timeout_ms}"
        )
    return args


# Main application engine.
engine: Engine = create_engine(
    _settings.database_url,
    pool_pre_ping=True,
    pool_size=_settings.db_pool_size,
    max_overflow=_settings.db_max_overflow,
    pool_timeout=_settings.db_pool_timeout_seconds,
    pool_recycle=_settings.db_pool_recycle_seconds,
    connect_args=_build_main_connect_args(),
    future=True,
)


# Dedicated engine for health/readiness checks.
#
# NullPool prevents reuse of stale connections, while connect_timeout
# ensures a network-level database failure becomes an exception instead
# of leaving the HTTP request hanging indefinitely.
health_engine: Engine = create_engine(
    _settings.database_url,
    poolclass=NullPool,
    connect_args={
        "connect_timeout": min(
            _settings.db_connect_timeout_seconds, 3
        ),
    },
    future=True,
)


SessionLocal: sessionmaker[Session] = sessionmaker(
    bind=engine,
    class_=Session,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


def get_db() -> Iterator[Session]:
    """Application database session dependency."""
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


def get_health_db() -> Iterator[Session]:
    """Dedicated database session dependency for readiness checks."""
    db = Session(bind=health_engine)

    try:
        yield db
    finally:
        db.close()
