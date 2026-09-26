from app.services.rag.normalization import (
    normalize_and_hash,
    normalize_query,
    query_hash,
)


def test_normalization_collapses_whitespace():
    assert normalize_query("  hello   world  ") == "hello world"


def test_normalization_merges_punctuation():
    assert normalize_query("hi!!?? there..") == "hi. there."


def test_hash_deterministic():
    a = query_hash("hello world")
    b = query_hash("hello world")
    assert a == b


def test_equivalent_queries_share_hash():
    _, h1 = normalize_and_hash("Hello   World")
    _, h2 = normalize_and_hash("hello world")
    assert h1 == h2
