from app.services.rag.decomposition import decompose_deterministic


def test_baseline_always_present():
    out = decompose_deterministic("something simple")
    assert any(d.intent == "background" for d in out)


def test_comparison_detected():
    out = decompose_deterministic("X vs Y comparison")
    assert any(d.intent == "comparison" for d in out)


def test_recent_detected():
    out = decompose_deterministic("recent advances in NLP")
    assert any(d.intent == "recent_evidence" for d in out)


def test_empty_query():
    assert decompose_deterministic("") == []
