from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.pdf_workspace import (
    PdfAnnotationCreate,
    PdfAnnotationRead,
    PdfAnnotationUpdate,
    PdfWorkspaceRead,
    PdfWorkspaceUpdate,
)
from app.services import pdf_workspace as pdf_service

router = APIRouter(prefix="/projects", tags=["pdf-workspace"])


def _workspace_response(state, documents, annotations) -> PdfWorkspaceRead:
    return PdfWorkspaceRead(
        id=state.id,
        project_id=state.project_id,
        active_file_id=state.active_file_id,
        page_number=state.page_number,
        zoom=state.zoom,
        scroll_x=state.scroll_x,
        scroll_y=state.scroll_y,
        documents=[pdf_service.document_read(file) for file in documents],
        annotations=[
            PdfAnnotationRead.model_validate(annotation)
            for annotation in annotations
        ],
        updated_at=state.updated_at,
    )


@router.get("/{project_id}/pdf-workspace", response_model=PdfWorkspaceRead)
def get_workspace(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PdfWorkspaceRead:
    state, documents, annotations = pdf_service.get_pdf_workspace(
        db,
        user_id=current_user.id,
        project_id=project_id,
    )
    return _workspace_response(state, documents, annotations)


@router.put("/{project_id}/pdf-workspace", response_model=PdfWorkspaceRead)
def save_workspace(
    project_id: uuid.UUID,
    payload: PdfWorkspaceUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PdfWorkspaceRead:
    pdf_service.save_pdf_workspace(
        db,
        user_id=current_user.id,
        project_id=project_id,
        active_file_id=payload.active_file_id,
        page_number=payload.page_number,
        zoom=payload.zoom,
        scroll_x=payload.scroll_x,
        scroll_y=payload.scroll_y,
    )
    state, documents, annotations = pdf_service.get_pdf_workspace(
        db,
        user_id=current_user.id,
        project_id=project_id,
    )
    return _workspace_response(state, documents, annotations)


@router.post(
    "/{project_id}/pdf-workspace/annotations",
    response_model=PdfAnnotationRead,
    status_code=status.HTTP_201_CREATED,
)
def create_annotation(
    project_id: uuid.UUID,
    payload: PdfAnnotationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PdfAnnotationRead:
    annotation = pdf_service.create_annotation(
        db,
        user_id=current_user.id,
        project_id=project_id,
        file_id=payload.file_id,
        kind=payload.kind,
        page_number=payload.page_number,
        selected_text=payload.selected_text,
        note=payload.note,
        rect=payload.rect,
    )
    return PdfAnnotationRead.model_validate(annotation)


@router.patch(
    "/{project_id}/pdf-workspace/annotations/{annotation_id}",
    response_model=PdfAnnotationRead,
)
def update_annotation(
    project_id: uuid.UUID,
    annotation_id: uuid.UUID,
    payload: PdfAnnotationUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PdfAnnotationRead:
    annotation = pdf_service.update_annotation(
        db,
        user_id=current_user.id,
        project_id=project_id,
        annotation_id=annotation_id,
        changes=payload.model_dump(exclude_unset=True),
    )
    return PdfAnnotationRead.model_validate(annotation)


@router.delete(
    "/{project_id}/pdf-workspace/annotations/{annotation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_annotation(
    project_id: uuid.UUID,
    annotation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    pdf_service.delete_annotation(
        db,
        user_id=current_user.id,
        project_id=project_id,
        annotation_id=annotation_id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
