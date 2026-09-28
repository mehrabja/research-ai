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

from app.domain.generation import GenerationProviderResult
from app.services.manuscript_prose.contracts import SectionContract
from app.services.manuscript_prose.evidence import EvidenceItem, EvidencePacket
from app.services.manuscript_prose import generator as prose_generator


def _provider_packet() -> tuple[SectionContract, EvidencePacket]:
    contract = SectionContract(
        section_key="intro",
        section_type="introduction",
        display_order=0,
        title="Introduction",
        purpose="Explain the topic",
        research_objective="Assess the evidence",
        requirement_keys=["r1"],
        citation_required=True,
        word_budget=300,
    )
    packet = EvidencePacket(
        section_key="intro",
        section_type="introduction",
        display_order=0,
        title="Introduction",
        research_objective="Assess the evidence",
        m28_items=[
            EvidenceItem(
                evidence_id=__import__("uuid").uuid4(),
                source_id=__import__("uuid").uuid4(),
                excerpt="The intervention improved the primary outcome.",
                rank=1,
                evidence_role="direct",
            )
        ],
    )
    return contract, packet


class _FakeProvider:
    provider_name = "fake"
    model_name = "fake-model"

    def __init__(self, text: str) -> None:
        self.text = text

    def generate(self, **kwargs):
        return GenerationProviderResult(
            text=self.text,
            provider=self.provider_name,
            model=self.model_name,
        )


def test_provider_assisted_generation_parses_structured_output(monkeypatch) -> None:
    contract, packet = _provider_packet()
    evidence_id = str(packet.m28_items[0].evidence_id)

    payload = (
        '{"section_id":"intro","paragraphs":[{"sentences":['
        '{"text":"The evidence supports the intervention.",'
        f'"evidence_refs":["{evidence_id}"]'
        '}]}]}'
    )
    monkeypatch.setattr(
        prose_generator,
        "_build_provider",
        lambda: (_FakeProvider(payload), object()),
    )

    result = prose_generator.generate_section(
        None, contract=contract, packet=packet, mode="provider_assisted"
    )
    assert result.mode_used == "provider_assisted"
    assert result.provider_name == "fake"
    assert result.unit.paragraphs[0].sentences[0].evidence_refs == [evidence_id]


def test_hybrid_provider_failure_falls_back_to_deterministic(monkeypatch) -> None:
    contract, packet = _provider_packet()

    monkeypatch.setattr(
        prose_generator,
        "_build_provider",
        lambda: (_FakeProvider("{not-json}"), object()),
    )

    result = prose_generator.generate_section(
        None, contract=contract, packet=packet, mode="hybrid"
    )
    assert result.mode_used == "deterministic"
    assert "provider_fallback" in result.warnings
    assert result.unit.paragraphs


def test_provider_assisted_invalid_output_raises(monkeypatch) -> None:
    contract, packet = _provider_packet()
    monkeypatch.setattr(
        prose_generator,
        "_build_provider",
        lambda: (_FakeProvider("{not-json}"), object()),
    )

    import pytest
    with pytest.raises(ValueError, match="invalid JSON"):
        prose_generator.generate_section(
            None,
            contract=contract,
            packet=packet,
            mode="provider_assisted",
        )
