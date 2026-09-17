from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Connection


def test_jobs_table_exists(conn: Connection) -> None:
    v = conn.execute(
        text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema='public' AND table_name='jobs'"
        )
    ).scalar()
    assert v == 1


def test_partial_unique_idempotency_index(conn: Connection) -> None:
    row = conn.execute(
        text(
            "SELECT indexdef FROM pg_indexes "
            "WHERE schemaname='public' "
            "AND indexname='ux_jobs_idempotency_key'"
        )
    ).scalar()
    assert row is not None
    assert "UNIQUE" in row
    assert "WHERE" in row


def test_ready_partial_index(conn: Connection) -> None:
    row = conn.execute(
        text(
            "SELECT indexdef FROM pg_indexes "
            "WHERE schemaname='public' AND indexname='ix_jobs_ready'"
        )
    ).scalar()
    assert row is not None
    assert "WHERE" in row


def test_stale_partial_index(conn: Connection) -> None:
    row = conn.execute(
        text(
            "SELECT indexdef FROM pg_indexes "
            "WHERE schemaname='public' AND indexname='ix_jobs_stale'"
        )
    ).scalar()
    assert row is not None
    assert "WHERE" in row


def test_attempt_count_check_exists(conn: Connection) -> None:
    row = conn.execute(
        text(
            "SELECT conname FROM pg_constraint "
            "WHERE conname='ck_jobs_attempt_within_max'"
        )
    ).scalar()
    assert row == "ck_jobs_attempt_within_max"


def test_processing_lease_check_exists(conn: Connection) -> None:
    row = conn.execute(
        text(
            "SELECT conname FROM pg_constraint "
            "WHERE conname='ck_jobs_processing_lease'"
        )
    ).scalar()
    assert row == "ck_jobs_processing_lease"


def test_fk_on_delete_set_null(conn: Connection) -> None:
    rows = conn.execute(
        text(
            "SELECT confdeltype FROM pg_constraint "
            "WHERE conrelid = 'jobs'::regclass AND contype = 'f'"
        )
    ).scalars().all()
    assert all(t == "n" for t in rows)
    assert len(rows) >= 2
