"""M20 — Worker handlers for code_analyze and data_profile jobs."""
from __future__ import annotations

import logging
import uuid

from app.core.exceptions import StorageUnavailable
from app.db.models.project_file import ProjectFile
from app.db.session import SessionLocal
from app.domain.jobs import JobContext
from app.services import code_intelligence as code_service
from app.services import data_intelligence as data_service
from app.services.file_storage import get_storage_provider

logger = logging.getLogger(__name__)


def handle_code_analyze(ctx: JobContext) -> None:
    file_id_raw = ctx.payload.get("file_id")
    if not file_id_raw:
        raise ValueError("code_analyze payload missing file_id")
    file_id = uuid.UUID(str(file_id_raw))

    with SessionLocal() as db:
        pf = db.get(ProjectFile, file_id)
        if pf is None or pf.deleted_at is not None:
            return
        provider = get_storage_provider()
        try:
            chunks = provider.open(key=pf.storage_key)
        except StorageUnavailable:
            raise
        code_service.analyze_file(
            db, project_file_id=file_id, chunks=chunks
        )


def handle_data_profile(ctx: JobContext) -> None:
    file_id_raw = ctx.payload.get("file_id")
    if not file_id_raw:
        raise ValueError("data_profile payload missing file_id")
    file_id = uuid.UUID(str(file_id_raw))

    with SessionLocal() as db:
        pf = db.get(ProjectFile, file_id)
        if pf is None or pf.deleted_at is not None:
            return
        provider = get_storage_provider()
        try:
            chunks = provider.open(key=pf.storage_key)
        except StorageUnavailable:
            raise
        data_service.profile_file(
            db, project_file_id=file_id, chunks=chunks
        )
