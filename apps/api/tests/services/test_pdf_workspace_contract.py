from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.exceptions import AppError

from app.schemas.pdf_workspace import PdfAnnotationCreate, PdfAnnotationRect
from app.services.pdf_workspace import _validate_annotation_payload


def test_highlight_requires_selected_text() -> None:
    with pytest.raises(AppError, match="selected_text"):
        _validate_annotation_payload(
            kind="highlight",
            selected_text=None,
            note=None,
        )


def test_note_requires_note() -> None:
    with pytest.raises(AppError, match="require note"):
        _validate_annotation_payload(
            kind="note",
            selected_text=None,
            note="   ",
        )


def test_pdf_annotation_rect_is_positive() -> None:
    with pytest.raises(ValidationError):
        PdfAnnotationRect(x=1, y=2, width=0, height=10)


def test_pdf_annotation_create_accepts_typed_rect() -> None:
    payload = PdfAnnotationCreate(
        file_id="00000000-0000-0000-0000-000000000001",
        kind="highlight",
        page_number=2,
        selected_text="important text",
        rect={"x": 10, "y": 20, "width": 50, "height": 12},
    )

    assert payload.rect is not None
    assert payload.rect.width == 50
    assert payload.rect.height == 12
