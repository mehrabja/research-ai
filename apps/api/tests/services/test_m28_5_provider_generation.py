"""Provider-assisted manuscript prose preserves evidence provenance."""
from __future__ import annotations

import uuid
from types import SimpleNamespace

from app.domain.generation import GenerationProviderResult
from app.services.manuscript_prose.contracts import SectionContract
from app.services.manuscript_prose.evidence import EvidenceItem, EvidencePacket
from app.services.manuscript_prose.generator import generate_section


class _FakeProvider:
    provider_name = "openrouter"
    model_name = "openai/gpt-4o-mini"

    def generate(self, *, system_prompt, user_prompt, temperature, max_output_tokens):
        return GenerationProviderResult(
            text='{{"paragraphs":[{{"paragraph":0,"sentences":[{{"index":0,"text":"Evidence-backed wording.","evidence_refs":["{}"]}}]}}]}}'.format(self.evidence_id),
            provider=self.provider_name,
            model=self.model_name,
            input_tokens=12,
            output_tokens=8,
        )


def test_provider_assisted_generation_keeps_evidence_refs(monkeypatch):
    evidence_id = uuid.uuid4()
    contract = SectionContract(
        section_key="results",
        section_type="results",
        display_order=0,
        title="Results",
        purpose="Report the observed result.",
        research_objective="Measure the observed effect.",
    )
    packet = EvidencePacket(
        section_key="results",
        section_type="results",
        display_order=0,
        title="Results",
        research_objective="Measure the observed effect.",
        m28_items=[
            EvidenceItem(
                evidence_id=evidence_id,
                source_id=None,
                excerpt="Observed effect was positive.",
                rank=1,
                evidence_role="direct",
            )
        ],
    )

    provider = _FakeProvider()
    provider.evidence_id = str(evidence_id)

    monkeypatch.setattr(
        "app.services.manuscript_prose.generator.build_generation_provider",
        lambda _profile: provider,
    )
    monkeypatch.setattr(
        "app.services.manuscript_prose.generator.execute_metered_provider_call",
        lambda call, **_kwargs: call(),
    )
    monkeypatch.setattr(
        "app.services.manuscript_prose.generator.get_settings",
        lambda: SimpleNamespace(
            manuscript_prose_provider="openrouter",
            manuscript_prose_model="openai/gpt-4o-mini",
            manuscript_prose_temperature=0.2,
            manuscript_prose_max_output_tokens=2000,
        ),
    )

    result = generate_section(
        None,
        contract=contract,
        packet=packet,
        mode="provider_assisted",
        workspace_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        report_id=uuid.uuid4(),
    )
    assert result.mode_used == "provider_assisted"
    assert result.unit.paragraphs[0].sentences[0].evidence_refs == [str(evidence_id)]
    assert result.unit.paragraphs[0].sentences[0].text == "Evidence-backed wording."
