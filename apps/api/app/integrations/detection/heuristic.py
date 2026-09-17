"""Heuristic detection baseline.

Honest placeholder — NOT a real AI detector. Computes a deterministic
signal from text statistics so the pipeline is exercisable
end-to-end without external dependencies.

The probability is a SIGNAL, not truth about whether text is
AI-generated.
"""
from __future__ import annotations

import re
import statistics

from app.domain.detection import DetectionProviderResult

_SENTENCE_SPLIT = re.compile(r"[.!?]+")
_AI_TELL_WORDS = frozenset({
    "delve", "tapestry", "navigate", "leverage", "facilitate",
    "furthermore", "moreover", "crucial", "robust", "seamlessly",
    "comprehensive", "pivotal", "holistic", "paradigm", "underscore",
})


class HeuristicDetectionProvider:
    provider_name = "heuristic"
    model_name = "baseline-v1"

    def detect(self, *, text: str) -> DetectionProviderResult:
        input_chars = len(text)

        sentences = [
            s.strip() for s in _SENTENCE_SPLIT.split(text) if s.strip()
        ]
        words = [w for w in re.split(r"\s+", text) if w]

        if not words:
            return DetectionProviderResult(
                provider=self.provider_name,
                model=self.model_name,
                probability=None,
                raw_label="unknown",
                details={"reason": "no_words"},
                input_chars=input_chars,
            )

        if len(sentences) >= 2:
            sent_lengths = [len(s.split()) for s in sentences]
            variance = statistics.pvariance(sent_lengths)
            uniformity = 1.0 - min(variance / 50.0, 1.0)
        else:
            uniformity = 0.5

        unique_ratio = len({w.lower() for w in words}) / len(words)
        lexical_signal = max(0.0, 1.0 - unique_ratio / 0.7)

        tell_count = sum(1 for w in words if w.lower() in _AI_TELL_WORDS)
        density = tell_count / max(len(words) / 100.0, 1.0)
        tell_signal = min(density, 1.0)

        probability = (
            0.35 * uniformity
            + 0.35 * lexical_signal
            + 0.30 * tell_signal
        )
        probability = max(0.0, min(1.0, probability))

        return DetectionProviderResult(
            provider=self.provider_name,
            model=self.model_name,
            probability=probability,
            raw_label=None,
            details={
                "uniformity": uniformity,
                "lexical_signal": lexical_signal,
                "tell_signal": tell_signal,
                "word_count": len(words),
            },
            input_chars=input_chars,
        )


__all__ = ["HeuristicDetectionProvider"]
