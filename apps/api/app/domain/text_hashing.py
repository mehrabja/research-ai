"""Canonical content hashing for extracted source text."""
from __future__ import annotations

import hashlib


def compute_content_hash(text: str) -> str:
    """Return lowercase hex SHA-256 of the UTF-8 encoding of ``text``.

    The input is expected to already be normalized (see
    ``text_normalization.normalize_text``). The hash therefore
    represents exactly the bytes stored in ``Source.full_text``.
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


__all__ = ["compute_content_hash"]
