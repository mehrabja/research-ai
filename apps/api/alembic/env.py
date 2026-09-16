"""Alembic environment for research-ai.

Resolution order for the SQLAlchemy URL:

1. ALEMBIC_DATABASE_URL (env)
2. DATABASE_URL          (env)
3. sqlalchemy.url in alembic.ini

The .env file at the repository root is loaded automatically if present.
"""

from __future__ import annotations

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool

# --- make the api package importable when running `alembic` from apps/api ---
API_DIR = Path(__file__).resolve().parent.parent

if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

# --- load .env from the monorepo root (../..) and from cwd ---
REPO_ROOT = API_DIR.parent.parent

load_dotenv(REPO_ROOT / ".env", override=False)
load_dotenv(API_DIR / ".env", override=False)

# --- import all models so Base.metadata is complete ---
import app.db.models  # noqa: F401,E402
from app.db.base import Base  # noqa: E402

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

_db_url = os.getenv("ALEMBIC_DATABASE_URL") or os.getenv("DATABASE_URL")

if _db_url:
    config.set_main_option("sqlalchemy.url", _db_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()