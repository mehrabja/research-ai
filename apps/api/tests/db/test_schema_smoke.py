"""Smoke tests: schema shape, extensions, migration head."""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Connection


REQUIRED_TABLES = {
    "users", "reports", "sources", "chunks",
    "generation_runs", "detection_runs", "detection_segments",
    "translation_runs", "translation_versions",
    "humanization_runs", "humanization_iterations", "humanization_rewrites",
    "convergence_runs", "convergence_iterations", "convergence_best_snapshots",
    "convergence_strategies",
    "voice_profiles", "style_exemplars", "ai_tell_patterns",
    "detection_thresholds", "terminology_glossary",
    "report_versions", "review_events", "citation_links",
    "jobs", "usage_logs", "model_pricing", "credit_transactions",
}


def test_required_tables_exist(conn: Connection) -> None:
    rows = conn.execute(
        text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"
        )
    ).scalars().all()
    present = set(rows)
    missing = REQUIRED_TABLES - present
    assert not missing, f"missing tables: {sorted(missing)}"


def test_required_extensions_exist(conn: Connection) -> None:
    rows = conn.execute(
        text("SELECT extname FROM pg_extension")
    ).scalars().all()
    assert "pgcrypto" in rows
    assert "vector" in rows


def test_alembic_version_is_present(conn: Connection) -> None:
    version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
    assert version == "0001_initial_schema"