"""DB-level CHECK tests for ``report_events``.

These tests exercise the CHECK constraints directly at the SQL level,
independent of the ORM or the service layer.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError


def _mk_user(conn: Connection) -> uuid.UUID:
    result = conn.execute(
        text(
            "INSERT INTO users (email, password_hash) "
            "VALUES (:e, 'h') RETURNING id"
        ),
        {"e": f"ev-{uuid.uuid4()}@example.com"},
    ).scalar()
    assert isinstance(result, uuid.UUID)
    return result


def _mk_report(conn: Connection, user_id: uuid.UUID) -> uuid.UUID:
    result = conn.execute(
        text(
            "INSERT INTO reports (user_id, topic, status, output_language) "
            "VALUES (:uid, 'T', 'draft', 'en') RETURNING id"
        ),
        {"uid": user_id},
    ).scalar()
    assert isinstance(result, uuid.UUID)
    return result


def _mk_version(
    conn: Connection, report_id: uuid.UUID, number: int = 1
) -> uuid.UUID:
    result = conn.execute(
        text(
            "INSERT INTO report_versions "
            "(report_id, version_number, language, content) "
            "VALUES (:rid, :n, 'en', 'x') RETURNING id"
        ),
        {"rid": report_id, "n": number},
    ).scalar()
    assert isinstance(result, uuid.UUID)
    return result


# ---- shape: status_transition ------------------------------------------

def test_status_transition_ok(conn: Connection) -> None:
    uid = _mk_user(conn)
    rid = _mk_report(conn, uid)
    conn.execute(
        text(
            "INSERT INTO report_events "
            "(report_id, user_id, event_type, from_status, to_status) "
            "VALUES (:r, :u, 'status_transition', 'draft', 'searching')"
        ),
        {"r": rid, "u": uid},
    )


def test_status_transition_with_version_id_rejected(conn: Connection) -> None:
    """The exact bug the previous CHECK missed."""
    uid = _mk_user(conn)
    rid = _mk_report(conn, uid)
    vid = _mk_version(conn, rid)
    with pytest.raises(IntegrityError):
        conn.execute(
            text(
                "INSERT INTO report_events "
                "(report_id, user_id, event_type, "
                " from_status, to_status, version_id) "
                "VALUES (:r, :u, 'status_transition', 'draft', 'searching', :v)"
            ),
            {"r": rid, "u": uid, "v": vid},
        )


def test_status_transition_same_status_rejected(conn: Connection) -> None:
    uid = _mk_user(conn)
    rid = _mk_report(conn, uid)
    with pytest.raises(IntegrityError):
        conn.execute(
            text(
                "INSERT INTO report_events "
                "(report_id, user_id, event_type, from_status, to_status) "
                "VALUES (:r, :u, 'status_transition', 'draft', 'draft')"
            ),
            {"r": rid, "u": uid},
        )


def test_status_transition_missing_from_status_rejected(
    conn: Connection,
) -> None:
    uid = _mk_user(conn)
    rid = _mk_report(conn, uid)
    with pytest.raises(IntegrityError):
        conn.execute(
            text(
                "INSERT INTO report_events "
                "(report_id, user_id, event_type, from_status, to_status) "
                "VALUES (:r, :u, 'status_transition', NULL, 'searching')"
            ),
            {"r": rid, "u": uid},
        )


def test_status_transition_missing_to_status_rejected(
    conn: Connection,
) -> None:
    uid = _mk_user(conn)
    rid = _mk_report(conn, uid)
    with pytest.raises(IntegrityError):
        conn.execute(
            text(
                "INSERT INTO report_events "
                "(report_id, user_id, event_type, from_status, to_status) "
                "VALUES (:r, :u, 'status_transition', 'draft', NULL)"
            ),
            {"r": rid, "u": uid},
        )


# ---- shape: version_created --------------------------------------------

def test_version_created_ok(conn: Connection) -> None:
    uid = _mk_user(conn)
    rid = _mk_report(conn, uid)
    vid = _mk_version(conn, rid)
    conn.execute(
        text(
            "INSERT INTO report_events "
            "(report_id, user_id, event_type, version_id) "
            "VALUES (:r, :u, 'version_created', :v)"
        ),
        {"r": rid, "u": uid, "v": vid},
    )


def test_version_created_without_version_id_rejected(
    conn: Connection,
) -> None:
    uid = _mk_user(conn)
    rid = _mk_report(conn, uid)
    with pytest.raises(IntegrityError):
        conn.execute(
            text(
                "INSERT INTO report_events "
                "(report_id, user_id, event_type) "
                "VALUES (:r, :u, 'version_created')"
            ),
            {"r": rid, "u": uid},
        )


def test_version_created_with_from_status_rejected(conn: Connection) -> None:
    uid = _mk_user(conn)
    rid = _mk_report(conn, uid)
    vid = _mk_version(conn, rid)
    with pytest.raises(IntegrityError):
        conn.execute(
            text(
                "INSERT INTO report_events "
                "(report_id, user_id, event_type, from_status, version_id) "
                "VALUES (:r, :u, 'version_created', 'draft', :v)"
            ),
            {"r": rid, "u": uid, "v": vid},
        )


def test_version_created_with_to_status_rejected(conn: Connection) -> None:
    uid = _mk_user(conn)
    rid = _mk_report(conn, uid)
    vid = _mk_version(conn, rid)
    with pytest.raises(IntegrityError):
        conn.execute(
            text(
                "INSERT INTO report_events "
                "(report_id, user_id, event_type, to_status, version_id) "
                "VALUES (:r, :u, 'version_created', 'searching', :v)"
            ),
            {"r": rid, "u": uid, "v": vid},
        )


# ---- shape: unknown event_type -----------------------------------------

def test_unknown_event_type_rejected(conn: Connection) -> None:
    uid = _mk_user(conn)
    rid = _mk_report(conn, uid)
    with pytest.raises(IntegrityError):
        conn.execute(
            text(
                "INSERT INTO report_events "
                "(report_id, user_id, event_type) "
                "VALUES (:r, :u, 'some_other_event')"
            ),
            {"r": rid, "u": uid},
        )


# ---- nullable user (system events) -------------------------------------

def test_event_user_id_nullable(conn: Connection) -> None:
    uid = _mk_user(conn)
    rid = _mk_report(conn, uid)
    conn.execute(
        text(
            "INSERT INTO report_events "
            "(report_id, user_id, event_type, from_status, to_status) "
            "VALUES (:r, NULL, 'status_transition', 'draft', 'cancelled')"
        ),
        {"r": rid},
    )
