from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import FileNotFound
from app.db.models.pdf_workspace import PdfAnnotation, PdfWorkspaceState
from app.db.models.project_file import ProjectFile
from app.schemas.pdf_workspace import PdfWorkspaceDocumentRead
from app.services import files as files_service
from app.services.projects import get_project

PDF_CONTENT_PREFIX = "/api/v1/files/"


def _ensure_pdf_file(
    db: Session,
    *,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
    file_id: uuid.UUID,
) -> ProjectFile:
    pf = files_service.get_file(db, user_id=user_id, file_id=file_id)
    if (
        pf.project_id != project_id
        or pf.file_kind != "pdf"
        or pf.deleted_at is not None
    ):
        raise FileNotFound("PDF file not found in this project.")
    return pf


def get_pdf_workspace(
    db: Session,
    *,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
) -> tuple[PdfWorkspaceState, list[ProjectFile], list[PdfAnnotation]]:
    get_project(db, user_id=user_id, project_id=project_id)
    state = db.execute(
        select(PdfWorkspaceState).where(
            PdfWorkspaceState.project_id == project_id
        )
    ).scalar_one_or_none()

    if state is None:
        state = PdfWorkspaceState(
            project_id=project_id,
            active_file_id=None,
            page_number=1,
            zoom=1.0,
            scroll_x=0.0,
            scroll_y=0.0,
        )
        db.add(state)
        db.commit()
        db.refresh(state)

    pdfs, _ = files_service.list_files(
        db,
        user_id=user_id,
        project_id=project_id,
        file_kind="pdf",
        limit=200,
        offset=0,
    )

    valid_ids = {pf.id for pf in pdfs}
    if state.active_file_id is not None and state.active_file_id not in valid_ids:
        state.active_file_id = None
        state.page_number = 1
        db.commit()
        db.refresh(state)

    annotations: list[PdfAnnotation] = []
    if state.active_file_id is not None:
        annotations = list(
            db.execute(
                select(PdfAnnotation)
                .where(
                    PdfAnnotation.project_id == project_id,
                    PdfAnnotation.file_id == state.active_file_id,
                )
                .order_by(
                    PdfAnnotation.page_number.asc(),
                    PdfAnnotation.created_at.asc(),
                    PdfAnnotation.id.asc(),
                )
            ).scalars().all()
        )

    return state, list(pdfs), annotations


def save_pdf_workspace(
    db: Session,
    *,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
    active_file_id: uuid.UUID | None,
    page_number: int,
    zoom: float,
    scroll_x: float,
    scroll_y: float,
) -> PdfWorkspaceState:
    get_project(db, user_id=user_id, project_id=project_id)
    if active_file_id is not None:
        _ensure_pdf_file(
            db,
            user_id=user_id,
            project_id=project_id,
            file_id=active_file_id,
        )

    state = db.execute(
        select(PdfWorkspaceState)
        .where(PdfWorkspaceState.project_id == project_id)
        .with_for_update()
    ).scalar_one_or_none()

    if state is None:
        state = PdfWorkspaceState(
            project_id=project_id,
            active_file_id=active_file_id,
            page_number=page_number,
            zoom=zoom,
            scroll_x=scroll_x,
            scroll_y=scroll_y,
        )
        db.add(state)
    else:
        state.active_file_id = active_file_id
        state.page_number = page_number
        state.zoom = zoom
        state.scroll_x = scroll_x
        state.scroll_y = scroll_y

    db.commit()
    db.refresh(state)
    return state


def create_annotation(
    db: Session,
    *,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
    file_id: uuid.UUID,
    kind: str,
    page_number: int,
    selected_text: str | None,
    note: str | None,
    rect: dict[str, Any] | None,
) -> PdfAnnotation:
    _ensure_pdf_file(
        db,
        user_id=user_id,
        project_id=project_id,
        file_id=file_id,
    )
    annotation = PdfAnnotation(
        project_id=project_id,
        file_id=file_id,
        created_by_user=user_id,
        kind=kind,
        page_number=page_number,
        selected_text=selected_text,
        note=note,
        rect=rect,
        annotation_meta={"source": "pdf_workspace"},
    )
    db.add(annotation)
    db.commit()
    db.refresh(annotation)
    return annotation


def get_annotation(
    db: Session,
    *,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
    annotation_id: uuid.UUID,
) -> PdfAnnotation:
    get_project(db, user_id=user_id, project_id=project_id)
    annotation = db.execute(
        select(PdfAnnotation).where(
            PdfAnnotation.id == annotation_id,
            PdfAnnotation.project_id == project_id,
        )
    ).scalar_one_or_none()
    if annotation is None:
        raise FileNotFound("PDF annotation not found.")
    return annotation


def update_annotation(
    db: Session,
    *,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
    annotation_id: uuid.UUID,
    changes: dict[str, Any],
) -> PdfAnnotation:
    annotation = get_annotation(
        db,
        user_id=user_id,
        project_id=project_id,
        annotation_id=annotation_id,
    )
    for key, value in changes.items():
        if value is not None:
            setattr(annotation, key, value)
    db.commit()
    db.refresh(annotation)
    return annotation


def delete_annotation(
    db: Session,
    *,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
    annotation_id: uuid.UUID,
) -> None:
    annotation = get_annotation(
        db,
        user_id=user_id,
        project_id=project_id,
        annotation_id=annotation_id,
    )
    db.delete(annotation)
    db.commit()


def document_read(file: ProjectFile) -> PdfWorkspaceDocumentRead:
    return PdfWorkspaceDocumentRead(
        id=file.id,
        original_filename=file.original_filename,
        size_bytes=file.size_bytes,
        status=file.status,
        extraction_status=file.extraction_status,
        content_url=PDF_CONTENT_PREFIX + str(file.id) + "/content",
    )
