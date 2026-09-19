"""M20 — Data Intelligence service.

Concurrency: same pattern as ``code_intelligence``.
"""
from __future__ import annotations

import logging
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import (
    DataProfileResourceLimit,
    DataProfileUnsupportedFormat,
    FileNotFound,
)
from app.db.models.data_profile import DataColumnProfile, DataProfile
from app.db.models.project_file import ProjectFile
from app.domain.data_intelligence import (
    DataFormat,
    ProfileStatus,
    detect_data_format,
)
from app.services.profilers import profile_data

logger = logging.getLogger(__name__)


def _read_bounded(
    chunks: Iterator[bytes], max_bytes: int
) -> tuple[bytes, bool]:
    buf = bytearray()
    for c in chunks:
        buf.extend(c)
        if len(buf) > max_bytes:
            return b"", True
    return bytes(buf), False


def _iter_once(data: bytes) -> Iterator[bytes]:
    step = 64 * 1024
    for i in range(0, len(data), step):
        yield data[i : i + step]


def _get_or_create_parent_locked(
    db: Session, *, project_file_id: uuid.UUID
) -> DataProfile:
    existing = db.execute(
        select(DataProfile)
        .where(DataProfile.project_file_id == project_file_id)
        .with_for_update()
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    settings = get_settings()
    placeholder = DataProfile(
        project_file_id=project_file_id,
        format=DataFormat.UNKNOWN.value,
        profile_status=ProfileStatus.PENDING.value,
        profile_version=settings.intelligence_analysis_version,
    )
    db.add(placeholder)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        winner = db.execute(
            select(DataProfile)
            .where(DataProfile.project_file_id == project_file_id)
            .with_for_update()
        ).scalar_one()
        return winner
    return placeholder


def profile_file(
    db: Session,
    *,
    project_file_id: uuid.UUID,
    chunks: Iterator[bytes],
) -> DataProfile:
    settings = get_settings()
    pf = db.get(ProjectFile, project_file_id)
    if pf is None:
        raise FileNotFound()

    fmt = detect_data_format(
        extension=pf.extension,
        mime=pf.detected_mime_type or pf.client_mime_type,
    )
    if fmt is DataFormat.UNKNOWN:
        raise DataProfileUnsupportedFormat(
            "data format could not be detected"
        )

    # --- Read + profile phase (no DB writes) ----------------------------
    data, too_large = _read_bounded(
        chunks, settings.document_max_bytes
    )
    if too_large:
        raise DataProfileResourceLimit(
            "data file exceeds document_max_bytes"
        )
    result = profile_data(chunks=_iter_once(data), fmt=fmt)

    status = (
        ProfileStatus.FAILED.value
        if result.error is not None
        else ProfileStatus.COMPLETED.value
    )

    quality = dict(result.quality or {})
    quality.setdefault("rows_scanned", result.row_count)
    quality["scan_truncated"] = bool(result.scan_truncated)

    # --- DB phase (locked) ----------------------------------------------
    profile = _get_or_create_parent_locked(
        db, project_file_id=project_file_id
    )

    db.execute(
        delete(DataColumnProfile).where(
            DataColumnProfile.data_profile_id == profile.id
        )
    )

    profile.format = fmt.value
    profile.profile_status = status
    profile.profile_error = result.error[:500] if result.error else None
    profile.profile_version = settings.intelligence_analysis_version
    profile.row_count = result.row_count
    profile.column_count = result.column_count
    profile.schema_data = result.schema_data
    profile.quality = quality
    profile.statistics = result.statistics
    profile.sample_rows = result.sample_rows
    profile.updated_at = datetime.now(UTC)
    db.flush()

    for c in result.columns:
        db.add(
            DataColumnProfile(
                data_profile_id=profile.id,
                name=c.name[:500],
                ordinal=c.ordinal,
                inferred_type=c.inferred_type,
                nullable=c.nullable,
                null_count=c.null_count,
                null_ratio=(
                    c.null_count / c.total_count
                    if c.total_count
                    else 0.0
                ),
                distinct_count=c.distinct_count,
                unique_ratio=c.unique_ratio,
                min_value=c.min_value,
                max_value=c.max_value,
                mean=c.mean,
                median=c.median,
                stddev=c.stddev,
                top_values=c.top_values,
                column_meta=c.meta,
            )
        )
    db.commit()
    db.refresh(profile)
    return profile


def get_profile(
    db: Session, *, user_id: uuid.UUID, file_id: uuid.UUID
) -> DataProfile | None:
    from app.services.files import get_file

    get_file(db, user_id=user_id, file_id=file_id)
    return db.execute(
        select(DataProfile).where(
            DataProfile.project_file_id == file_id
        )
    ).scalar_one_or_none()


def list_columns(
    db: Session,
    *,
    profile_id: uuid.UUID,
    limit: int = 200,
    offset: int = 0,
) -> tuple[list[DataColumnProfile], int]:
    base = select(DataColumnProfile).where(
        DataColumnProfile.data_profile_id == profile_id
    )
    total = int(
        db.execute(
            select(func.count()).select_from(base.subquery())
        ).scalar_one()
    )
    rows = (
        db.execute(
            base.order_by(
                DataColumnProfile.ordinal.asc(),
                DataColumnProfile.id.asc(),
            )
            .limit(limit)
            .offset(offset)
        )
        .scalars()
        .all()
    )
    return list(rows), total
