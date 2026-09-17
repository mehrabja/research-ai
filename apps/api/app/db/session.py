"""SQLAlchemy engine, session factories, and FastAPI dependencies."""
from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from app.core.config import get_settings

_settings = get_settings()


# Main application engine.
engine: Engine = create_engine(
    _settings.database_url,
    pool_pre_ping=True,
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
    connect_args={"connect_timeout": 3},
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
