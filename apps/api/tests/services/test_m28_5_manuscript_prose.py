"""M28.5 — domain + serialization + validation tests."""
from __future__ import annotations

from app.domain.manuscript_prose import (
    M28_5_VERSION,
    PROSE_GENERATION_MODES,
    PROSE_RUN_STATUSES,
    is_special_section,
    weakest_tier,
)
from app.services.manuscript_prose.serialization import (
    ParagraphUnit,
    SectionUnit,
    SentenceUnit,
    join_paragraphs,
    join_sentences,
    layout_section,
    normalize_text,
    split_sentences,
    word_count,
)
from app.services.manuscript_prose.validation import validate_section


def test_version() -> None:
    assert M28_5_VERSION == "m28.5.1"


def test_modes() -> None:
    assert set(PROSE_GENERATION_MODES) == {
        "deterministic", "provider_assisted", "hybrid",
    }


def test_run_statuses() -> None:
    assert "completed" in PROSE_RUN_STATUSES
    assert "partial" in PROSE_RUN_STATUSES


def test_special_sections() -> None:
    assert is_special_section("abstract")
    assert not is_special_section("methods")


def test_weakest_tier() -> None:
    assert weakest_tier("direct") == "direct"
    assert weakest_tier("direct", "partial") == "partial"
    assert weakest_tier("direct", "context_only") == "context_only"
    assert weakest_tier(None, None) == "context_only"


def test_normalize() -> None:
    assert normalize_text("  hello   world \n") == "hello world"


def test_split_and_join_sentences() -> None:
    text = "First sentence. Second! Third?"
    sents = split_sentences(text)
    assert len(sents) == 3
    assert join_sentences(sents) == text


def test_word_count_unicode() -> None:
    assert word_count("hello world") == 2
    assert word_count("سلام دنیا") == 2
    assert word_count("") == 0


def test_join_paragraphs() -> None:
    assert join_paragraphs(["a", "b"]) == "a\n\nb"
    assert join_paragraphs(["a", "", "b"]) == "a\n\nb"


def test_layout_section_assigns_positions() -> None:
    unit = SectionUnit(
        section_key="intro", section_type="introduction",
        display_order=0, title="Intro",
        paragraphs=[
            ParagraphUnit(
                ordinal=0, text="", char_start=0, char_end=0,
                sentences=[
                    SentenceUnit(
                        text="First.", char_start=0, char_end=0,
                    ),
                    SentenceUnit(
                        text="Second.", char_start=0, char_end=0,
                    ),
                ],
            )
        ],
    )
    cursor, end = layout_section(unit, 0)
    assert unit.paragraphs[0].sentences[0].char_start == 0
    assert unit.paragraphs[0].sentences[0].char_end == 6
    assert unit.paragraphs[0].sentences[1].char_start == 7
    assert end > 0


def test_validate_section_unknown_evidence() -> None:
    unit = SectionUnit(
        section_key="intro", section_type="introduction",
        display_order=0, title="Intro",
        paragraphs=[
            ParagraphUnit(
                ordinal=0, text="body", char_start=0, char_end=4,
                sentences=[
                    SentenceUnit(
                        text="X.", char_start=0, char_end=2,
                        evidence_refs=["bogus-id"],
                    )
                ],
            )
        ],
    )
    outcome = validate_section(
        unit,
        known_evidence_ids={"real-id"},
        known_citation_ids=set(),
        max_words=100,
    )
    assert outcome.status == "invalid"
    assert any("unknown_evidence_ref" in e for e in outcome.errors)


def test_validate_section_word_budget() -> None:
    unit = SectionUnit(
        section_key="intro", section_type="introduction",
        display_order=0, title="Intro",
        paragraphs=[
            ParagraphUnit(
                ordinal=0, text="a b c d e f", char_start=0, char_end=11,
                sentences=[
                    SentenceUnit(
                        text="a b c d e f",
                        char_start=0, char_end=11,
                    )
                ],
            )
        ],
    )
    outcome = validate_section(
        unit, known_evidence_ids=set(), known_citation_ids=set(),
        max_words=3,
    )
    assert outcome.status == "invalid"
