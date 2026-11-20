"""M19 — bytes-based extraction adapter.

M8 (app/services/extraction.py) extracts from a URL for a Source.
M19 extracts from bytes already stored for a ProjectFile. The input
contracts are different; M8 is not duplicated.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from html import unescape
from io import BytesIO

from pypdf import PdfReader

from app.domain.file import FileKind

EXTRACTION_PIPELINE_VERSION = "m19.1"
_MAX_EXTRACTED_CHARS = 5_000_000


@dataclass(frozen=True)
class ExtractionResult:
    supported: bool
    text: str | None = None
    meta: dict = field(default_factory=dict)
    error: str | None = None


def extract_bytes(
    *, content: bytes, kind: FileKind, mime: str | None
) -> ExtractionResult:
    if kind == FileKind.PDF:
        return _extract_pdf(content)
    if kind == FileKind.TEXT:
        return _extract_text(content)
    if kind == FileKind.DOCUMENT and mime in (
        "text/html",
        "application/xhtml+xml",
    ):
        return _extract_html(content)
    return ExtractionResult(supported=False)


def _extract_pdf(content: bytes) -> ExtractionResult:
    try:
        reader = PdfReader(BytesIO(content), strict=False)
        if reader.is_encrypted:
            return ExtractionResult(
                supported=True, text="", error="encrypted_pdf"
            )

        pages: list[str] = []
        total = 0
        for page in reader.pages:
            page_text = page.extract_text() or ""
            total += len(page_text)
            if total > _MAX_EXTRACTED_CHARS:
                break
            pages.append(page_text)

        metadata = reader.metadata or {}
        return ExtractionResult(
            supported=True,
            text="\n\n".join(pages).strip(),
            meta={
                "page_count": len(reader.pages),
                "title": metadata.get("/Title") or None,
                "author": metadata.get("/Author") or None,
            },
        )
    except Exception:
        # Keep parser internals out of API-facing error values.
        return ExtractionResult(
            supported=True, text="", error="pdf_parse_failed"
        )


def _extract_text(content: bytes) -> ExtractionResult:
    """Strict UTF-8 / UTF-16 detection. No lossy fallback."""
    if content.startswith(b"\xef\xbb\xbf"):
        try:
            text = content[3:].decode("utf-8")
        except UnicodeDecodeError as exc:
            return ExtractionResult(
                supported=True, text="", error=f"utf8_decode_failed: {exc}"
            )
        return ExtractionResult(
            supported=True,
            text=text[:_MAX_EXTRACTED_CHARS],
            meta={"encoding": "utf-8-sig"},
        )
    if content.startswith(b"\xff\xfe") or content.startswith(b"\xfe\xff"):
        try:
            text = content.decode("utf-16")
        except UnicodeDecodeError as exc:
            return ExtractionResult(
                supported=True, text="", error=f"utf16_decode_failed: {exc}"
            )
        return ExtractionResult(
            supported=True,
            text=text[:_MAX_EXTRACTED_CHARS],
            meta={"encoding": "utf-16"},
        )
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        return ExtractionResult(
            supported=True, text="", error=f"utf8_decode_failed: {exc}"
        )
    return ExtractionResult(
        supported=True,
        text=text[:_MAX_EXTRACTED_CHARS],
        meta={"encoding": "utf-8"},
    )


_TAG_RE = re.compile(r"<[^>]+>")


def _extract_html(content: bytes) -> ExtractionResult:
    raw = content.decode("utf-8", errors="replace")
    text = _TAG_RE.sub(" ", raw)
    text = unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return ExtractionResult(supported=True, text=text[:_MAX_EXTRACTED_CHARS])
