"""M36 — Request context tests."""
from __future__ import annotations

from app.core.request_context import (
    generate_request_id,
    get_request_id,
    reset_request_id,
    sanitize_request_id,
    set_request_id,
)


def test_generated_id_is_hex() -> None:
    rid = generate_request_id()
    assert len(rid) == 32
    int(rid, 16)


def test_sanitize_accepts_safe() -> None:
    assert (
        sanitize_request_id("abc-123_XYZ:1.2")
        == "abc-123_XYZ:1.2"
    )


def test_sanitize_rejects_spaces() -> None:
    assert sanitize_request_id("bad value") is None


def test_sanitize_rejects_oversize() -> None:
    assert sanitize_request_id("a" * 200) is None


def test_sanitize_rejects_empty() -> None:
    assert sanitize_request_id("") is None
    assert sanitize_request_id(None) is None


def test_set_get_reset_roundtrip() -> None:
    token = set_request_id("rid-1")
    try:
        assert get_request_id() == "rid-1"
    finally:
        reset_request_id(token)
    assert get_request_id() is None
