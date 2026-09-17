"""Document text extractors.

Each extractor returns an ``ExtractedDocument`` (defined in the domain
layer) containing raw, un-normalized page text. Normalization and
canonical offsets are the domain's responsibility.

Supported content types in this milestone:
  * application/pdf  (pymupdf)
  * text/html, application/xhtml+xml  (BeautifulSoup + html.parser)
  * text/plain       (UTF-8 first, replacement fallback)
"""
from __future__ import annotations

import logging
from typing import Protocol

import fitz  # pymupdf
from bs4 import BeautifulSoup

from app.domain.extraction_types import (
    ExtractedDocument,
    ExtractedPage,
)

logger = logging.getLogger(__name__)


class ExtractorError(Exception):
    """Base for parser-level errors."""


class ParseFetcherError(ExtractorError):
    """Malformed or unreadable document."""


class EmptyDocumentError(ExtractorError):
    """Parsing succeeded but produced no usable text."""


class DocumentExtractor(Protocol):
    supported_content_types: tuple[str, ...]

    def extract(
        self, *, content: bytes, content_type: str
    ) -> ExtractedDocument: ...


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------
class PdfExtractor:
    supported_content_types: tuple[str, ...] = ("application/pdf",)

    def extract(
        self, *, content: bytes, content_type: str
    ) -> ExtractedDocument:
        try:
            doc = fitz.open(stream=content, filetype="pdf")
        except Exception as exc:
            raise ParseFetcherError("failed to open PDF") from exc

        try:
            if doc.is_encrypted:
                raise ParseFetcherError("encrypted PDF")
            pages: list[ExtractedPage] = []
            for page_index in range(doc.page_count):
                try:
                    page_text = (
                        doc.load_page(page_index).get_text("text") or ""
                    )
                except Exception as exc:
                    raise ParseFetcherError(
                        f"failed to extract page {page_index + 1}"
                    ) from exc
                pages.append(
                    ExtractedPage(
                        page_number=page_index + 1,
                        raw_text=page_text,
                    )
                )
        finally:
            doc.close()

        return ExtractedDocument(
            content_type=content_type,
            pages=pages,
            metadata={},
        )


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------
class HtmlExtractor:
    supported_content_types: tuple[str, ...] = (
        "text/html",
        "application/xhtml+xml",
    )

    def extract(
        self, *, content: bytes, content_type: str
    ) -> ExtractedDocument:
        try:
            html = content.decode("utf-8")
        except UnicodeDecodeError:
            html = content.decode("utf-8", errors="replace")

        try:
            soup = BeautifulSoup(html, "html.parser")
        except Exception as exc:
            raise ParseFetcherError("failed to parse HTML") from exc

        for tag in soup(
            ["script", "style", "noscript", "template", "svg", "head"]
        ):
            tag.decompose()
        for tag in soup(["nav", "header", "footer", "aside"]):
            tag.decompose()

        text = soup.get_text(separator="\n")
        return ExtractedDocument(
            content_type=content_type,
            pages=[ExtractedPage(page_number=None, raw_text=text)],
            metadata={},
        )


# ---------------------------------------------------------------------------
# Plain text
# ---------------------------------------------------------------------------
class PlainTextExtractor:
    supported_content_types: tuple[str, ...] = ("text/plain",)

    def extract(
        self, *, content: bytes, content_type: str
    ) -> ExtractedDocument:
        try:
            text = content.decode("utf-8")
            encoding = "utf-8"
        except UnicodeDecodeError:
            text = content.decode("utf-8", errors="replace")
            encoding = "utf-8-replace"
        return ExtractedDocument(
            content_type=content_type,
            pages=[ExtractedPage(page_number=None, raw_text=text)],
            metadata={"encoding": encoding},
        )


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------
_EXTRACTORS: tuple[DocumentExtractor, ...] = (
    PdfExtractor(),
    HtmlExtractor(),
    PlainTextExtractor(),
)


def get_extractor(content_type: str) -> DocumentExtractor | None:
    """Return the extractor for a normalized content type, or None.

    Normalization strips parameters such as ``; charset=utf-8`` and
    lower-cases the result. Unknown types return ``None`` — never a
    silent fallback to plain text.
    """
    normalized = content_type.split(";", 1)[0].strip().lower()
    for extractor in _EXTRACTORS:
        if normalized in extractor.supported_content_types:
            return extractor
    return None


__all__ = [
    "DocumentExtractor",
    "EmptyDocumentError",
    "ExtractorError",
    "HtmlExtractor",
    "ParseFetcherError",
    "PdfExtractor",
    "PlainTextExtractor",
    "get_extractor",
]
