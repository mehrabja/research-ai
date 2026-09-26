"""M30 — Unicode-safe identity tests."""
from __future__ import annotations

from app.domain.citation import identity_key_for


def test_same_doi_same_key() -> None:
    assert identity_key_for(
        doi="10.1/x", title="A", authors=["X"], year=2020,
    ) == identity_key_for(
        doi="10.1/x", title="B", authors=["Y"], year=2021,
    )


def test_unicode_title_stable() -> None:
    a = identity_key_for(
        doi=None, title="سلام دنیا", authors=["نویسنده"], year=2020,
    )
    b = identity_key_for(
        doi=None, title="  سلام دنیا ", authors=["نویسنده"],
        year=2020,
    )
    assert a == b


def test_unicode_title_not_empty_canonical() -> None:
    from app.domain.citation import canonical_title
    assert canonical_title("日本語") == "日本語"
    assert canonical_title("кириллица") == "кириллица"
    assert canonical_title("café") == "café"
