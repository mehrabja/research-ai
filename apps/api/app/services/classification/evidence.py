"""M21 — Bounded evidence emitters."""
from __future__ import annotations

from dataclasses import dataclass

from app.core.config import get_settings


@dataclass(frozen=True)
class EvidenceItem:
    target: str
    signal_type: str
    source_location: str
    matched_text: str
    weight: float
    target_code: str | None = None


class EvidenceCollector:
    def __init__(self) -> None:
        self._items: list[EvidenceItem] = []
        self._settings = get_settings()

    def add(self, item: EvidenceItem) -> None:
        if (
            len(self._items)
            >= self._settings.classification_max_evidence_items
        ):
            return
        trunc = self._settings.classification_max_evidence_chars
        if len(item.matched_text) > trunc:
            item = EvidenceItem(
                target=item.target,
                signal_type=item.signal_type,
                source_location=item.source_location,
                matched_text=item.matched_text[:trunc],
                weight=item.weight,
                target_code=item.target_code,
            )
        self._items.append(item)

    def items(self) -> list[EvidenceItem]:
        return list(self._items)

    def items_for(self, target: str) -> list[EvidenceItem]:
        return [e for e in self._items if e.target == target]
