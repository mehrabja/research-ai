"""M20 — Intelligence routes."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.exceptions import (
    CodeAnalysisNotFound,
    DataProfileNotFound,
)
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.intelligence import (
    CodeAnalysisRead,
    CodeDependencyListResponse,
    CodeDependencyRead,
    CodeSymbolListResponse,
    CodeSymbolRead,
    DataColumnListResponse,
    DataColumnProfileRead,
    DataProfileRead,
)
from app.services import code_intelligence as code_service
from app.services import data_intelligence as data_service

router = APIRouter(prefix="/files", tags=["intelligence"])


@router.get(
    "/{file_id}/code-analysis",
    response_model=CodeAnalysisRead,
    summary="Get code analysis for a file",
)
def get_code_analysis(
    file_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CodeAnalysisRead:
    analysis = code_service.get_analysis(
        db, user_id=current_user.id, file_id=file_id
    )
    if analysis is None:
        raise CodeAnalysisNotFound()
    return CodeAnalysisRead.model_validate(analysis)


@router.get(
    "/{file_id}/code-symbols",
    response_model=CodeSymbolListResponse,
    summary="List code symbols for a file's analysis",
)
def list_code_symbols(
    file_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> CodeSymbolListResponse:
    analysis = code_service.get_analysis(
        db, user_id=current_user.id, file_id=file_id
    )
    if analysis is None:
        raise CodeAnalysisNotFound()
    rows, total = code_service.list_symbols(
        db, analysis_id=analysis.id, limit=limit, offset=offset
    )
    return CodeSymbolListResponse(
        items=[CodeSymbolRead.model_validate(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{file_id}/code-dependencies",
    response_model=CodeDependencyListResponse,
    summary="List code dependencies for a file's analysis",
)
def list_code_dependencies(
    file_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> CodeDependencyListResponse:
    analysis = code_service.get_analysis(
        db, user_id=current_user.id, file_id=file_id
    )
    if analysis is None:
        raise CodeAnalysisNotFound()
    rows, total = code_service.list_dependencies(
        db, analysis_id=analysis.id, limit=limit, offset=offset
    )
    return CodeDependencyListResponse(
        items=[CodeDependencyRead.model_validate(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{file_id}/data-profile",
    response_model=DataProfileRead,
    summary="Get data profile for a file",
)
def get_data_profile(
    file_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DataProfileRead:
    profile = data_service.get_profile(
        db, user_id=current_user.id, file_id=file_id
    )
    if profile is None:
        raise DataProfileNotFound()
    return DataProfileRead.model_validate(profile)


@router.get(
    "/{file_id}/data-columns",
    response_model=DataColumnListResponse,
    summary="List column profiles for a file's data profile",
)
def list_data_columns(
    file_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> DataColumnListResponse:
    profile = data_service.get_profile(
        db, user_id=current_user.id, file_id=file_id
    )
    if profile is None:
        raise DataProfileNotFound()
    rows, total = data_service.list_columns(
        db, profile_id=profile.id, limit=limit, offset=offset
    )
    return DataColumnListResponse(
        items=[DataColumnProfileRead.model_validate(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )
