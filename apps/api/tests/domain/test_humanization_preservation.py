from app.domain.humanization_preservation import (
    extract_protected_tokens,
    validate_preservation,
)


def test_evidence_preserved():
    b = extract_protected_tokens("Result [E1] and [E2].")
    a = extract_protected_tokens("Findings [E1] indicate [E2].")
    assert validate_preservation(b, a).ok


def test_evidence_removed():
    b = extract_protected_tokens("R [E1] [E2].")
    a = extract_protected_tokens("R [E1].")
    assert not validate_preservation(b, a).ok


def test_evidence_invented():
    b = extract_protected_tokens("R [E1].")
    a = extract_protected_tokens("R [E1] [E99].")
    assert not validate_preservation(b, a).ok


def test_url_preserved():
    b = extract_protected_tokens("See https://example.com/a.")
    a = extract_protected_tokens("Refer to https://example.com/a.")
    assert validate_preservation(b, a).ok


def test_doi_changed():
    b = extract_protected_tokens("Study 10.1234/abcd.5678.")
    a = extract_protected_tokens("Study 10.1234/xyz.")
    assert not validate_preservation(b, a).ok


def test_number_mutation():
    b = extract_protected_tokens("Increase of 15%.")
    a = extract_protected_tokens("Increase of 51%.")
    assert not validate_preservation(b, a).ok


def test_glossary_preserved():
    b = extract_protected_tokens("Use aspirin.", glossary_terms=("aspirin",))
    a = extract_protected_tokens("Use aspirin now.", glossary_terms=("aspirin",))
    assert validate_preservation(b, a).ok


def test_glossary_changed():
    b = extract_protected_tokens("Use aspirin.", glossary_terms=("aspirin",))
    a = extract_protected_tokens("Use ibuprofen.", glossary_terms=("aspirin",))
    assert not validate_preservation(b, a).ok
