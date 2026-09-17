"""M16 — Translation preservation domain tests."""
from __future__ import annotations

from app.domain.translation_preservation import (
    check_glossary_terms,
    extract_token_counts,
    validate_translation_preservation,
)

# -------- evidence markers ------------------------------------------------

def test_evidence_markers_preserved():
    result = validate_translation_preservation(
        source_text="Findings [E1] and [E2] agree.",
        target_text="یافته‌ها [E1] و [E2] موافقند.",
    )
    assert result.ok
    assert result.evidence_markers.source_count == 2
    assert result.evidence_markers.target_count == 2


def test_evidence_marker_removed():
    result = validate_translation_preservation(
        source_text="Findings [E1] and [E2] agree.",
        target_text="یافته‌ها [E1] موافقند.",
    )
    assert not result.ok
    assert "[E2]" in result.evidence_markers.missing


def test_evidence_marker_duplicate_preserved():
    """[E1] [E1] must be distinguished from [E1]."""
    result = validate_translation_preservation(
        source_text="See [E1] [E1] and [E2].",
        target_text="ببین [E1] و [E2].",
    )
    assert not result.ok
    assert "[E1]" in result.evidence_markers.missing


def test_evidence_marker_duplicate_ok():
    result = validate_translation_preservation(
        source_text="See [E1] [E1].",
        target_text="ببین [E1] [E1].",
    )
    assert result.ok


def test_evidence_marker_invented():
    result = validate_translation_preservation(
        source_text="Findings [E1].",
        target_text="یافته‌ها [E1] و [E99].",
    )
    assert not result.ok
    assert "[E99]" in result.evidence_markers.added


# -------- urls ------------------------------------------------------------

def test_url_preserved():
    result = validate_translation_preservation(
        source_text="See https://example.com/a for details.",
        target_text="ببین https://example.com/a برای جزئیات.",
    )
    assert result.ok


def test_url_changed():
    result = validate_translation_preservation(
        source_text="See https://example.com/a.",
        target_text="ببین https://example.com/b.",
    )
    assert not result.ok


# -------- dois ------------------------------------------------------------

def test_doi_preserved():
    result = validate_translation_preservation(
        source_text="Study 10.1234/abcd.5678 shows.",
        target_text="مطالعه 10.1234/abcd.5678 نشان می‌دهد.",
    )
    assert result.ok


def test_doi_changed():
    result = validate_translation_preservation(
        source_text="Study 10.1234/abcd.5678 shows.",
        target_text="مطالعه 10.1234/xyz نشان می‌دهد.",
    )
    assert not result.ok


# -------- numbers ---------------------------------------------------------

def test_number_preserved():
    result = validate_translation_preservation(
        source_text="Increase of 15% in 2024 across 17 participants.",
        target_text="افزایش 15% در 2024 در بین 17 شرکت‌کننده.",
    )
    assert result.ok


def test_number_mutation_rejected():
    result = validate_translation_preservation(
        source_text="Increase of 15% observed.",
        target_text="افزایش 51% مشاهده شد.",
    )
    assert not result.ok
    assert "15%" in result.numbers.missing
    assert "51%" in result.numbers.added


def test_number_duplicate_preserved():
    result = validate_translation_preservation(
        source_text="17 and 17 participants.",
        target_text="17 و 17 شرکت‌کننده.",
    )
    assert result.ok


# -------- glossary --------------------------------------------------------

def test_glossary_satisfied():
    pairs = [("machine learning", "یادگیری ماشین")]
    result = validate_translation_preservation(
        source_text="We used machine learning for this task.",
        target_text="ما از یادگیری ماشین برای این کار استفاده کردیم.",
        glossary_pairs=pairs,
    )
    assert result.ok
    assert result.glossary.checked == 1


def test_glossary_violated():
    pairs = [("machine learning", "یادگیری ماشین")]
    result = validate_translation_preservation(
        source_text="We used machine learning for this task.",
        target_text="ما از ML برای این کار استفاده کردیم.",
        glossary_pairs=pairs,
    )
    assert not result.ok
    assert len(result.glossary.violations) == 1
    assert result.glossary.violations[0].source_term == "machine learning"


def test_glossary_absent_source_not_required():
    pairs = [("machine learning", "یادگیری ماشین")]
    result = validate_translation_preservation(
        source_text="Unrelated sentence.",
        target_text="جمله نامرتبط.",
        glossary_pairs=pairs,
    )
    assert result.ok
    assert result.glossary.checked == 0


def test_check_glossary_terms_direct():
    section = check_glossary_terms(
        source_text="ML is useful.",
        target_text="یادگیری ماشین مفید است.",
        pairs=[("ML", "یادگیری ماشین")],
    )
    assert section.ok
    assert section.checked == 1


# -------- extract ---------------------------------------------------------

def test_extract_token_counts_basic():
    counts = extract_token_counts("A [E1] B [E1] [E2] https://x.io 12%")
    assert counts.evidence_markers["[E1]"] == 2
    assert counts.evidence_markers["[E2]"] == 1
    assert counts.urls["https://x.io"] == 1
    assert counts.numbers["12%"] == 1
