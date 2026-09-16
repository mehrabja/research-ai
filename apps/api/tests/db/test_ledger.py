"""Verify credit_transactions reconstructs a balance."""
from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.engine import Connection


BALANCE_SQL = text(
    """
    SELECT COALESCE(SUM(CASE
        WHEN type IN ('purchase','release','refund') THEN amount
        WHEN type IN ('reserve','settlement') THEN -amount
    END), 0) AS balance
    FROM credit_transactions
    WHERE user_id = :uid AND status = 'posted'
    """
)


def _mk_user(conn: Connection) -> uuid.UUID:
    return conn.execute(
        text(
            "INSERT INTO users (email, password_hash) "
            "VALUES (:e, 'h') RETURNING id"
        ),
        {"e": f"ledger-{uuid.uuid4()}@example.com"},
    ).scalar()


def test_balance_reconstructs_from_ledger(conn: Connection) -> None:
    user_id = _mk_user(conn)

    conn.execute(
        text(
            "INSERT INTO credit_transactions "
            "(user_id, type, amount, currency, status) "
            "VALUES (:uid, 'purchase', 100, 'USD', 'posted')"
        ),
        {"uid": user_id},
    )

    conn.execute(
        text(
            "INSERT INTO credit_transactions "
            "(user_id, type, amount, currency, status) "
            "VALUES (:uid, 'reserve', 30, 'USD', 'posted')"
        ),
        {"uid": user_id},
    )

    conn.execute(
        text(
            "INSERT INTO credit_transactions "
            "(user_id, type, amount, currency, status) "
            "VALUES (:uid, 'settlement', 20, 'USD', 'posted')"
        ),
        {"uid": user_id},
    )

    conn.execute(
        text(
            "INSERT INTO credit_transactions "
            "(user_id, type, amount, currency, status) "
            "VALUES (:uid, 'release', 10, 'USD', 'posted')"
        ),
        {"uid": user_id},
    )

    conn.execute(
        text(
            "INSERT INTO credit_transactions "
            "(user_id, type, amount, currency, status) "
            "VALUES (:uid, 'purchase', 999, 'USD', 'pending')"
        ),
        {"uid": user_id},
    )

    balance = conn.execute(BALANCE_SQL, {"uid": user_id}).scalar()

    # 100 - 30 - 20 + 10 = 60
    assert Decimal(balance) == Decimal("60")


def test_amount_must_be_non_negative(conn: Connection) -> None:
    import pytest
    from sqlalchemy.exc import IntegrityError

    user_id = _mk_user(conn)

    with pytest.raises(IntegrityError):
        conn.execute(
            text(
                "INSERT INTO credit_transactions "
                "(user_id, type, amount, currency) "
                "VALUES (:uid, 'purchase', -1, 'USD')"
            ),
            {"uid": user_id},
        )