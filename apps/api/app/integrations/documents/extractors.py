"""Document text extractors.

Each extractor returns an ExtractedDocument containing raw,
un-normalized page text. Normalization and canonical offsets belong to
the domain layer.

Supported content types in this milestone:
  * application/pdf (pypdf)
  * text/html, application/xhtml+xml (BeautifulSoup + html.parser)
  * text/plain (UTF-8 first, replacement fallback)
"""
from __future__ import annotations

import logging
from io import BytesIO
from typing import Protocol

from bs4 import BeautifulSoup
from pypdf import PdfReader

from app.domain.extraction_types import ExtractedDocument, ExtractedPage

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


class PdfExtractor:
    supported_content_types: tuple[str, ...] = ("application/pdf",)

    def extract(
        self, *, content: bytes, content_type: str
    ) -> ExtractedDocument:
        try:
            reader = PdfReader(BytesIO(content), strict=False)
            if reader.is_encrypted:
                raise ParseFetcherError("encrypted PDF")

            pages: list[ExtractedPage] = []
            for page_index, page in enumerate(reader.pages):
                try:
                    page_text = page.extract_text() or ""
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
        except ParseFetcherError:
            raise
        except Exception as exc:
            raise ParseFetcherError("failed to open or read PDF") from exc

        return ExtractedDocument(
            content_type=content_type,
            pages=pages,
            metadata={},
        )


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


_EXTRACTORS: tuple[DocumentExtractor, ...] = (
    PdfExtractor(),
    HtmlExtractor(),
    PlainTextExtractor(),
)


def get_extractor(content_type: str) -> DocumentExtractor | None:
    """Return the extractor for a normalized content type, or None.

    Normalization strips parameters such as '; charset=utf-8' and
    lower-cases the result. Unknown types return None — never a silent
    fallback to plain text.
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
