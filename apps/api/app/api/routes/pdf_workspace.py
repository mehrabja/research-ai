from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.models.pdf_workspace import PdfAnnotation
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.pdf_workspace import (
    PdfAnnotationCreate,
    PdfAnnotationRead,
    PdfAnnotationUpdate,
    PdfWorkspaceRead,
    PdfWorkspaceUpdate,
)
from app.services import files as files_service
from app.services import pdf_workspace as pdf_service

router = APIRouter(prefix="/projects", tags=["pdf-workspace"])


def _workspace_response(
    state,
    documents,
    annotations,
) -> PdfWorkspaceRead:
    return PdfWorkspaceRead(
        id=state.id,
        project_id=state.project_id,
        active_file_id=state.active_file_id,
        page_number=state.page_number,