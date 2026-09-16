"""Constraint tests: UUID, email uniqueness, statuses, checks, uniqueness."""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.engine import Connection


def test_uuid_default_is_server_side(conn: Connection) -> None:
    row = conn.execute(
        text(
            "INSERT INTO users (email, password_hash) "
            "VALUES ('uuid-test@example.com', 'x') RETURNING id"
        )
    ).scalar()
    assert isinstance(row, uuid.UUID)


def test_email_lower_unique(conn: Connection) -> None:
    conn.execute(
        text("INSERT INTO users (email, password_hash) VALUES ('a@x.com', 'h')")
    )
    with pytest.raises(IntegrityError):
        conn.execute(
            text("INSERT INTO users (email, password_hash) VALUES ('A@X.COM', 'h')")
        )


def test_report_valid_status(conn: Connection) -> None:
    user_id = conn.execute(
        text(
            "INSERT INTO users (email, password_hash) "
            "VALUES ('report-ok@example.com', 'h') RETURNING id"
        )
    ).scalar()
    conn.execute(
        text(
            "INSERT INTO reports (user_id, topic, status, output_language) "
            "VALUES (:uid, 'T', 'draft', 'en')"
        ),
        {"uid": user_id},
    )


def test_report_invalid_status_rejected(conn: Connection) -> None:
    user_id = conn.execute(
        text(
            "INSERT INTO users (email, password_hash) "
            "VALUES ('report-bad@example.com', 'h') RETURNING id"
        )
    ).scalar()
    with pytest.raises(IntegrityError):
        conn.execute(
            text(
                "INSERT INTO reports (user_id, topic, status, output_language) "
                "VALUES (:uid, 'T', 'not_a_real_status', 'en')"
            ),
            {"uid": user_id},
        )


def _mk_report(conn: Connection) -> uuid.UUID:
    user_id = conn.execute(
        text(
            "INSERT INTO users (email, password_hash) "
            "VALUES (:e, 'h') RETURNING id"
        ),
        {"e": f"src-{uuid.uuid4()}@example.com"},
    ).scalar()
    return conn.execute(
        text(
            "INSERT INTO reports (user_id, topic, status, output_language) "
            "VALUES (:uid, 'T', 'draft', 'en') RETURNING id"
        ),
        {"uid": user_id},
    ).scalar()


def test_source_invalid_year_rejected(conn: Connection) -> None:
    report_id = _mk_report(conn)
    with pytest.raises(IntegrityError):
        conn.execute(
            text(
                "INSERT INTO sources (report_id, title, status, year) "
                "VALUES (:rid, 'T', 'metadata_only', 999)"
            ),
            {"rid": report_id},
        )


def test_source_negative_citation_count_rejected(conn: Connection) -> None:
    report_id = _mk_report(conn)
    with pytest.raises(IntegrityError):
        conn.execute(
            text(
                "INSERT INTO sources (report_id, title, status, citation_count) "
                "VALUES (:rid, 'T', 'metadata_only', -1)"
            ),
            {"rid": report_id},
        )


def test_source_quality_out_of_range_rejected(conn: Connection) -> None:
    report_id = _mk_report(conn)
    with pytest.raises(IntegrityError):
        conn.execute(
            text(
                "INSERT INTO sources (report_id, title, status, source_quality) "
                "VALUES (:rid, 'T', 'metadata_only', 1.5)"
            ),
            {"rid": report_id},
        )


def test_chunk_source_index_unique(conn: Connection) -> None:
    report_id = _mk_report(conn)
    source_id = conn.execute(
        text(
            "INSERT INTO sources (report_id, title, status) "
            "VALUES (:rid, 'T', 'full_text') RETURNING id"
        ),
        {"rid": report_id},
    ).scalar()
    conn.execute(
        text(
            "INSERT INTO chunks (source_id, content, chunk_index) "
            "VALUES (:sid, 'a', 0)"
        ),
        {"sid": source_id},
    )
    with pytest.raises(IntegrityError):
        conn.execute(
            text(
                "INSERT INTO chunks (source_id, content, chunk_index) "
                "VALUES (:sid, 'b', 0)"
            ),
            {"sid": source_id},
        )


def test_report_version_unique(conn: Connection) -> None:
    report_id = _mk_report(conn)
    conn.execute(
        text(
            "INSERT INTO report_versions (report_id, version_number, language, content) "
            "VALUES (:rid, 1, 'en', 'v1')"
        ),
        {"rid": report_id},
    )
    with pytest.raises(IntegrityError):
        conn.execute(
            text(
                "INSERT INTO report_versions (report_id, version_number, language, content) "
                "VALUES (:rid, 1, 'en', 'v1-dup')"
            ),
            {"rid": report_id},
        )


def test_jobs_idempotency_unique(conn: Connection) -> None:
    conn.execute(
        text(
            "INSERT INTO jobs (phase, status, idempotency_key) "
            "VALUES ('discovery', 'pending', 'k-1')"
        )
    )
    with pytest.raises(IntegrityError):
        conn.execute(
            text(
                "INSERT INTO jobs (phase, status, idempotency_key) "
                "VALUES ('discovery', 'pending', 'k-1')"
            )
        )


def test_money_columns_are_numeric(conn: Connection) -> None:
    rows = conn.execute(
        text(
            """
            SELECT table_name, column_name, data_type
            FROM information_schema.columns
            WHERE table_schema='public'
              AND (
                (table_name='usage_logs' AND column_name IN ('cost_usd_raw','cost_usd_charged'))
             OR (table_name='model_pricing' AND column_name IN ('input_price','output_price'))
             OR (table_name='credit_transactions' AND column_name = 'amount')
             OR (table_name='humanization_runs' AND column_name = 'cost_usd')
             OR (table_name='convergence_runs' AND column_name = 'total_cost_usd')
              )
            """
        )
    ).all()
    assert rows, "expected money columns to be present"
    for _tbl, col, dtype in rows:
        assert dtype == "numeric", f"{col} should be NUMERIC, got {dtype}"


def test_application_timestamps_are_timestamptz(conn: Connection) -> None:
    bad = conn.execute(
        text(
            """
            SELECT table_name, column_name, data_type
            FROM information_schema.columns
            WHERE table_schema='public'
              AND column_name IN ('created_at','updated_at','completed_at',
                                  'started_at','calibrated_at',
                                  'effective_from','effective_to')
              AND data_type <> 'timestamp with time zone'
            """
        )
    ).all()
    assert not bad, f"non-timestamptz application timestamps: {bad}"


def test_audit_tables_do_not_cascade(conn: Connection) -> None:
    rows = conn.execute(
        text(
            """
            SELECT tc.table_name, rc.delete_rule
            FROM information_schema.referential_constraints rc
            JOIN information_schema.table_constraints tc
              ON tc.constraint_name = rc.constraint_name
            WHERE rc.delete_rule = 'CASCADE'
              AND tc.table_name IN (
                'generation_runs','detection_runs','translation_runs',
                'humanization_runs','convergence_runs','report_versions',
                'usage_logs','credit_transactions','review_events'
              )
            """
        )
    ).all()
    assert not rows, f"audit tables must not cascade: {rows}"