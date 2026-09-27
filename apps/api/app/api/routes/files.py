"""M19 — File routes."""
from __future__ import annotations

import uuid
from collections.abc import Iterator

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.api.rate_limit_deps import enforce_user_rate_limit
from app.core.config import get_settings
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.project_file import (
    ProjectFileListItem,
    ProjectFileListResponse,
    ProjectFileRead,
)
from app.services import files as files_service

router = APIRouter(prefix="/projects", tags=["files"])
files_router = APIRouter(prefix="/files", tags=["files"])


@router.post(
    "/{project_id}/files",
    response_model=ProjectFileRead,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a file into a project",
    dependencies=[
        Depends(
            enforce_user_rate_limit(
                "files_upload",
                setting_name="rate_limit_upload_per_minute",
            )
        )
    ],
)
def upload_file(
    project_id: uuid.UUID,
    file: UploadFile = File(...),
    folder_id: uuid.UUID | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectFileRead:
    # بدنه بدون تغییر
    settings = get_settings()
    chunk_size = settings.file_chunk_stream_size

    def _stream() -> Iterator[bytes]:
        while True:
            chunk = file.file.read(chunk_size)
            if not chunk:
                break
            yield chunk

    pf = files_service.upload_file(
        db,
        user_id=current_user.id,
        project_id=project_id,
        original_filename=file.filename or "",
        client_mime=file.content_type,
        upload_stream=_stream(),
        folder_id=folder_id,
    )
    return ProjectFileRead.model_validate(pf)


@router.get(
    "/{project_id}/files",
    response_model=ProjectFileListResponse,
    summary="List files in a project",
)
def list_files(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    status_filter: str | None = Query(default=None, alias="status"),
    kind: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    folder_id: uuid.UUID | None = Query(default=None),
) -> ProjectFileListResponse:
    rows, total = files_service.list_files(
        db,
        user_id=current_user.id,
        project_id=project_id,
        status=status_filter,
        file_kind=kind,
        limit=limit,
        offset=offset,
        folder_id=folder_id,
    )
    return ProjectFileListResponse(
        items=[ProjectFileListItem.model_validate(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@files_router.get(
    "/{file_id}",
    response_model=ProjectFileRead,
    summary="Get file metadata",
)
def get_file(
    file_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectFileRead:
    pf = files_service.get_file(db, user_id=current_user.id, file_id=file_id)
    return ProjectFileRead.model_validate(pf)


@files_router.get("/{file_id}/content", summary="Download file content")
def download_file(
    file_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    pf, stream = files_service.open_content(
        db, user_id=current_user.id, file_id=file_id
    )
    media = (
        pf.detected_mime_type
        or pf.client_mime_type
        or "application/octet-stream"
    )
    headers = {
        "Content-Disposition":
            f'attachment; filename="{pf.normalized_filename}"',
        "Content-Length": str(pf.size_bytes),
        "X-Content-Type-Options": "nosniff",
    }
    return StreamingResponse(stream, media_type=media, headers=headers)

@files_router.delete(
    "/{file_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-delete a file",
)
def delete_file(
    file_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    files_service.delete_file(db, user_id=current_user.id, file_id=file_id)
