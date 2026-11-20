"""Regression tests for the pypdf-backed source and file extractors."""
from __future__ import annotations

from io import BytesIO

from pypdf import PdfWriter

from app.domain.file import FileKind
from app.integrations.documents.extractors import ParseFetcherError, PdfExtractor
from app.services.file_extraction import extract_bytes


def _make_pdf(*, encrypted: bool = False) -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    if encrypted:
        writer.encrypt("test-password")
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def test_source_pdf_extractor_preserves_page_boundaries() -> None:
    result = PdfExtractor().extract(
        content=_make_pdf(),
        content_type="application/pdf",
    )

    assert len(result.pages) == 1
    assert result.pages[0].page_number == 1
    assert result.pages[0].raw_text == ""


def test_source_pdf_extractor_rejects_encrypted_pdf() -> None:
    try:
        PdfExtractor().extract(
            content=_make_pdf(encrypted=True),
            content_type="application/pdf",
        )
    except ParseFetcherError as exc:
        assert "encrypted" in str(exc).lower()
    else:
        raise AssertionError("encrypted PDFs must be rejected")


def test_source_pdf_extractor_extracts_page_text(monkeypatch) -> None:
    class FakePage:
        def extract_text(self) -> str:
            return "Hello Research AI"

    class FakeReader:
        is_encrypted = False
        pages = [FakePage()]

    monkeypatch.setattr(
        "app.integrations.documents.extractors.PdfReader",
        lambda *_args, **_kwargs: FakeReader(),
    )
    result = PdfExtractor().extract(
        content=b"%PDF-fake",
        content_type="application/pdf",
    )

    assert result.pages[0].raw_text == "Hello Research AI"


def test_uploaded_pdf_extractor_returns_page_count_and_text(monkeypatch) -> None:
    class FakePage:
        def extract_text(self) -> str:
            return "Hello Research AI"

    class FakeReader:
        is_encrypted = False
        pages = [FakePage()]
        metadata = {"/Title": "Research", "/Author": "Test"}

    monkeypatch.setattr(
        "app.services.file_extraction.PdfReader",
        lambda *_args, **_kwargs: FakeReader(),
    )
    result = extract_bytes(
        content=b"%PDF-fake",
        kind=FileKind.PDF,
        mime="application/pdf",
    )

    assert result.supported is True
    assert result.error is None
    assert result.text == "Hello Research AI"
    assert result.meta["page_count"] == 1
    assert result.meta["title"] == "Research"
    assert result.meta["author"] == "Test"


def test_uploaded_pdf_extractor_rejects_encrypted_pdf() -> None:
    result = extract_bytes(
        content=_make_pdf(encrypted=True),
        kind=FileKind.PDF,
        mime="application/pdf",
    )

    assert result.supported is True
    assert result.text == ""
    assert result.error == "encrypted_pdf"


def test_uploaded_pdf_extractor_rejects_corrupt_pdf() -> None:
    result = extract_bytes(
        content=b"%PDF-1.4\nnot a valid PDF body",
        kind=FileKind.PDF,
        mime="application/pdf",
    )

    assert result.supported is True
    assert result.text == ""
    assert result.error == "pdf_parse_failed"


def test_source_pdf_extractor_rejects_corrupt_pdf() -> None:
    try:
        PdfExtractor().extract(
            content=b"%PDF-1.4\nnot a valid PDF body",
            content_type="application/pdf",
        )
    except ParseFetcherError:
        return
    raise AssertionError("corrupt PDFs must be rejected")
