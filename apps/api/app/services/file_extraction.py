"""M19 — bytes-based extraction adapter.

M8 (``app/services/extraction.py``) extracts from a URL for a Source.
M19 extracts from bytes already stored for a ProjectFile. Different
input contracts; M8 is not duplicated.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from html import unescape

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
        import fitz
    except ImportError as exc:
        return ExtractionResult(supported=False, error=str(exc))
    try:
        doc = fitz.open(stream=content, filetype="pdf")
    except Exception as exc:  # noqa: BLE001
        return ExtractionResult(supported=True, text="", error=str(exc))
    try:
        pages: list[str] = []
        total = 0
        for page in doc:
            t = page.get_text() or ""
            total += len(t)
            if total > _MAX_EXTRACTED_CHARS:
                break
            pages.append(t)
        text = "\n\n".join(pages).strip()
        doc_meta = doc.metadata or {}
        return ExtractionResult(
            supported=True,
            text=text,
            meta={
                "page_count": doc.page_count,
                "title": doc_meta.get("title") or None,
                "author": doc_meta.get("author") or None,
            },
        )
    finally:
        doc.close()


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
