"""Deterministic text normalization.

Preserves meaning: never rewrites wording, numbers, punctuation, or
scientific notation. Only removes surface noise that varies between
otherwise-equivalent documents.

The output is the canonical stored ``Source.full_text`` and the input
to ``compute_content_hash``.
"""
from __future__ import annotations

import re
import unicodedata

_KEEP_CONTROL = {"\n", "\t"}
_HORIZONTAL_WS = re.compile(r"[ \t]+")
_EXCESS_NEWLINES = re.compile(r"\n{3,}")


def normalize_text(text: str) -> str:
    if not text:
        return ""

    # 1. Unicode normalize to NFC.
    text = unicodedata.normalize("NFC", text)

    # 2. Normalize line endings.
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # 3. Drop null bytes and control chars except tab/newline.
    text = "".join(
        ch
        for ch in text
        if ch in _KEEP_CONTROL or unicodedata.category(ch)[0] != "C"
    )

    # 4. Collapse horizontal whitespace.
    text = _HORIZONTAL_WS.sub(" ", text)

    # 5. Collapse excessive blank lines.
    text = _EXCESS_NEWLINES.sub("\n\n", text)

    # 6. Trim leading/trailing.
    return text.strip()


__all__ = ["normalize_text"]
