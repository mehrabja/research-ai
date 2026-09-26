"""M30 — domain primitives."""
from __future__ import annotations

from app.domain.citation import (
    M30_VERSION,
    canonical_doi,
    canonical_title,
    claim_hash_for,
    identity_key_for,
    is_supporting,
)


def test_version_pinned() -> None:
    assert M30_VERSION == "m30.1"


def test_canonical_doi() -> None:
    assert canonical_doi("https://doi.org/10.1/AbC") == "10.1/abc"
    assert canonical_doi("doi:10.1/X") == "10.1/x"
    assert canonical_doi(None) is None


def test_canonical_title_unicode_preserved() -> None:
    assert canonical_title("The Title!") == "the title"
    # Persian must NOT be ASCII-folded
    assert canonical_title("سلام دنیا") == "سلام دنیا"
    assert canonical_title("日本語") == "日本語"


def test_identity_key_prefers_doi() -> None:
    a = identity_key_for(
        doi="10.1/x", title="A", authors=["X"], year=2020,
    )
    b = identity_key_for(
        doi="https://doi.org/10.1/X", title="B", authors=["Y"],
        year=2021,
    )
    assert a == b


def test_identity_key_title_author_year() -> None:
    a = identity_key_for(
        doi=None, title="T", authors=["Foo"], year=2020,
    )
    b = identity_key_for(
        doi=None, title=" t ", authors=["foo"], year=2020,
    )
    assert a == b


def test_claim_hash_deterministic() -> None:
    h1 = claim_hash_for(
        manuscript_version_id="v1", section_id="s1", text="Hello",
    )
    h2 = claim_hash_for(
        manuscript_version_id="v1", section_id="s1", text="  hello  ",
    )
    assert h1 == h2


def test_support_predicate() -> None:
    assert is_supporting("supports")
    assert is_supporting("partially_supports")
    assert not is_supporting("context_only")
