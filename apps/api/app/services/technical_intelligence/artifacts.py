"""M29 — Bounded raw artifact reader. No code execution."""
from __future__ import annotations

import logging
import uuid

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import TechnicalIntelligenceInvalid
from app.db.models.project_file import ProjectFile
from app.services.file_storage import get_storage_provider

logger = logging.getLogger(__name__)


def iter_project_file_bytes(
    db: Session, *, project_file_id: uuid.UUID,
):
    """Yield bounded chunks of bytes for a ProjectFile via the
    repository storage provider. No user context required."""
    pf = db.get(ProjectFile, project_file_id)
    if pf is None or pf.deleted_at is not None:
        raise TechnicalIntelligenceInvalid("project_file not found")

    storage_key = getattr(pf, "storage_key", None)
    if not storage_key:
        raise TechnicalIntelligenceInvalid(
            "project_file has no storage_key"
        )

    provider = get_storage_provider()
    yield from provider.open(key=storage_key)


def read_bounded(
    db: Session, *, project_file_id: uuid.UUID, max_bytes: int,
) -> tuple[bytes, bool]:
    buf = bytearray()
    for c in iter_project_file_bytes(
        db, project_file_id=project_file_id
    ):
        buf.extend(c)
        if len(buf) > max_bytes:
            return b"", True
    return bytes(buf), False


def max_result_bytes() -> int:
    s = get_settings()
    return int(getattr(s, "data_json_max_bytes", s.document_max_bytes))


__all__ = [
    "iter_project_file_bytes", "read_bounded", "max_result_bytes",
]
